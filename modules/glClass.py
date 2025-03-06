import tkinter as tk
import numpy as np
import time
from PIL import Image, ImageTk
import ctypes
import platform
import threading
import queue
import moderngl
import os

class OffscreenRenderer:
    """ModernGL offscreen renderer that doesn't require a window"""
    
    def __init__(self, width=640, height=480):
        self.width = width
        self.height = height
        
        # Create standalone context (doesn't need a window)
        self.ctx = moderngl.create_context(standalone=True, require=330)
        
        # Initialize texture and shader state
        self.textures = [None, None]
        self.mix_ratio = 0.0
        self.rot = 0.0
        self.hue = 0.0
        self.sat = 1.0
        self.val = 1.0
        self.hsvToggle = 0.0
        
        # Initialize shaders, buffers and textures
        self.init_resources()
        
        # Performance tracking
        self.frame_count = 0
        self.fps = 0
        self.fps_start_time = time.time()
        
        # Animation timing
        self.start_time = 0
        self.current_time = 0
        
        # Create framebuffer for offscreen rendering
        self.fbo = self.ctx.framebuffer(
            color_attachments=[self.ctx.texture((width, height), 3)]
        )
        self.set_shader()
    
    def init_resources(self):
        """Initialize shaders, buffers and textures."""
        # Shader program
        self.prog = self.ctx.program(
            vertex_shader="""
                #version 330
                
                in vec3 position;
                in vec2 texcoord;
                
                out vec2 TexCoord;
                
                void main() {
                    gl_Position = vec4(position, 1.0);
                    TexCoord = texcoord;
                }
            """,
            fragment_shader="""
                #version 330
                
                in vec2 TexCoord;
                
                uniform sampler2D textureSampler1;
                uniform sampler2D textureSampler2;
                uniform float time;
                uniform float mixRatio;
                uniform float rot;
                uniform float hue;
                uniform float sat;
                uniform float val;
                uniform float hsvToggle;
                
                out vec4 FragColor;
                
                // HSV to RGB conversion function
                vec3 hsv2rgb(vec3 c) {
                    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
                    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
                    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
                }
                
                // RGB to HSV conversion function
                vec3 rgb2hsv(vec3 c) {
                    vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
                    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
                    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
                    
                    float d = q.x - min(q.w, q.y);
                    float e = 1.0e-10;
                    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
                }
                
                void main() {
                    // Create rotation matrix
                    float angle = rot;
                    vec2 center = vec2(0.5, 0.5);
                    vec2 tc = TexCoord - center;
                    vec2 rotated = vec2(
                        tc.x * cos(angle) - tc.y * sin(angle),
                        tc.x * sin(angle) + tc.y * cos(angle)
                    );
                    vec2 rotatedTexCoord = rotated + center;
                    
                    // Sample both textures
                    vec4 texColor1 = texture(textureSampler1, TexCoord);
                    vec4 texColor2 = texture(textureSampler2, rotatedTexCoord);
                    
                    // Animated mix ratio (can be overridden by uniform)
                    float animatedMix = (sin(time) + 1.0) / 2.0;
                    float currentMix = mixRatio > 0.0 ? mixRatio : animatedMix;
                    
                    // Blend the two textures
                    vec4 blendedColor = mix(texColor1, texColor2, currentMix);
                    
                    // Apply HSV adjustment if enabled
                    if (hsvToggle > 0.5) {
                        vec3 hsvColor = rgb2hsv(blendedColor.rgb);
                        hsvColor.x = mod(hsvColor.x + hue, 1.0);  // Hue adjustment
                        hsvColor.y *= sat;                         // Saturation adjustment
                        hsvColor.z *= val;                         // Value adjustment
                        blendedColor.rgb = hsv2rgb(hsvColor);
                    }
                    
                    // Example effect: Vignette
                    float dist = distance(TexCoord, center);
                    float vignette = smoothstep(0.5, 0.2, dist);
                    
                    // Apply vignette
                    vec3 finalColor = blendedColor.rgb * vignette;
                    
                    FragColor = vec4(finalColor, blendedColor.a);
                }
            """
        )
        
        # Create vertices, normals and texture coordinates for a quad
        vertices = np.array([
            # x, y, z, tx, ty
            -1.0, -1.0, 0.0, 0.0, 0.0,
             1.0, -1.0, 0.0, 1.0, 0.0,
             1.0,  1.0, 0.0, 1.0, 1.0,
            -1.0,  1.0, 0.0, 0.0, 1.0,
        ], dtype='f4')
        
        # Create indices for two triangles
        indices = np.array([
            0, 1, 2,  # First triangle
            0, 2, 3   # Second triangle
        ], dtype='i4')
        
        # Create vertex buffer
        self.vbo = self.ctx.buffer(vertices)
        
        # Create index buffer
        self.ibo = self.ctx.buffer(indices)
        
        # Create vertex array
        self.vao = self.ctx.vertex_array(
            self.prog,
            [
                (self.vbo, '3f 2f', 'position', 'texcoord')
            ],
            self.ibo
        )
        
        # Create empty textures
        for i in range(2):
            self.textures[i] = self.ctx.texture((1, 1), 3)
            self.textures[i].filter = moderngl.LINEAR, moderngl.LINEAR
            self.textures[i].write(np.array([0, 0, 0], dtype='u1').tobytes())
        
        # Set uniform locations
        self.prog['textureSampler1'] = 0
        self.prog['textureSampler2'] = 1
    
    def update_texture(self, image, texture_index=0):
        """Updates one of the OpenGL textures with a new image."""
        if texture_index not in [0, 1]:
            raise ValueError("texture_index must be 0 or 1")
            
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize for performance if needed
        max_size = 2048
        if image.width > max_size or image.height > max_size:
            # Calculate new size preserving aspect ratio
            aspect = image.width / image.height
            if image.width > image.height:
                new_width = max_size
                new_height = int(max_size / aspect)
            else:
                new_height = max_size
                new_width = int(max_size * aspect)
            image = image.resize((new_width, new_height))
        
        # Update the texture
        if self.textures[texture_index]:
            # Create new texture with correct size if needed
            if self.textures[texture_index].size != image.size:
                self.textures[texture_index].release()
                self.textures[texture_index] = self.ctx.texture(image.size, 3)
                self.textures[texture_index].filter = moderngl.LINEAR, moderngl.LINEAR
            
            # Write image data to texture
            self.textures[texture_index].write(image.tobytes())
    
    def set_size(self, width, height):
        """Resize the offscreen framebuffer."""
        if width <= 0 or height <= 0:
            return
            
        if width == self.width and height == self.height:
            return
            
        self.width = width
        self.height = height
        
        # Recreate framebuffer with new size
        if hasattr(self, 'fbo'):
            self.fbo.release()
        
        self.fbo = self.ctx.framebuffer(
            color_attachments=[self.ctx.texture((width, height), 3)]
        )
    
    def set_shader(self, vertex_source_or_file="default.vert", fragment_source_or_file="default.frag", is_file=True):
        print("set shader")
        vertex_source_or_file = f"assets/shaders/{vertex_source_or_file}"
        fragment_source_or_file = f"assets/shaders/{fragment_source_or_file}"
        """Set custom shader code to be used for rendering.
        
        Args:
            vertex_source_or_file: Vertex shader source code or filename
            fragment_source_or_file: Fragment shader source code or filename
            is_file: If True, parameters are treated as filenames to load
        """
        try:
            # Load shader sources
            vertex_source = vertex_source_or_file
            fragment_source = fragment_source_or_file
            
            if is_file:
                # Load from files
                try:
                    with open(vertex_source_or_file, 'r') as f:
                        vertex_source = f.read()
                    with open(fragment_source_or_file, 'r') as f:
                        fragment_source = f.read()
                except FileNotFoundError as e:
                    print(f"Error loading shader files: {e}")
                    return
                except Exception as e:
                    print(f"Error reading shader files: {e}")
                    return
            
            # Release old program if it exists
            if hasattr(self, 'prog') and self.prog:
                self.prog.release()
            
            # Create new shader program
            self.prog = self.ctx.program(
                vertex_shader=vertex_source,
                fragment_shader=fragment_source
            )
            
            # Re-set uniform locations
            self.prog['textureSampler1'] = 0
            self.prog['textureSampler2'] = 1
            
        except Exception as e:
            print(f"Error setting shader: {e}")
            import traceback
            traceback.print_exc()
    
    def render(self):
        """Render the scene and return the resulting image."""
        # Update time uniform for animations
        if not hasattr(self, "start_time") or self.start_time == 0:
            self.start_time = time.time()
        self.current_time = time.time() - self.start_time
        
        # Set uniforms
        try:
            # These are the core uniforms we expect in every shader
            self.prog['textureSampler1'] = 0
            self.prog['textureSampler2'] = 1
            
            # These are optional and might not be in all shaders
            try: self.prog['time'].value = self.current_time
            except: pass
            
            try: self.prog['mixRatio'].value = self.mix_ratio
            except: pass
            
            try: self.prog['rot'].value = self.rot
            except: pass
            
            try: self.prog['hue'].value = self.hue
            except: pass
            
            try: self.prog['sat'].value = self.sat
            except: pass
            
            try: self.prog['val'].value = self.val
            except: pass
            
            try: self.prog['hsvToggle'].value = self.hsvToggle
            except: pass
        except Exception as e:
            print(f"Error setting uniforms during render: {e}")
        
        # Bind textures
        self.textures[0].use(location=0)
        self.textures[1].use(location=1)
        
        # Use the framebuffer
        self.fbo.use()
        
        # Clear screen
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)
        
        # Render the quad
        self.vao.render()
        
        # Read the resulting pixels
        pixels = self.fbo.read(components=3)
        
        # Convert to PIL Image
        return Image.frombytes('RGB', (self.width, self.height), pixels, 'raw', 'RGB', 0, -1)


class ModernGLTkFrame(tk.Frame):
    """A Tkinter frame for displaying ModernGL-rendered content
    that works on all platforms."""
    
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        
        # Set default size
        self.width = kwargs.get('width', 640)
        self.height = kwargs.get('height', 480)
        
        # Create canvas for drawing
        self.canvas = tk.Canvas(self, width=self.width, height=self.height, 
                               highlightthickness=0, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Create renderer thread and communication queue
        self.render_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.exit_flag = threading.Event()
        self.renderer = None
        self.gl_initialized = False
        
        # Start the renderer thread
        self.start_renderer_thread()
        
        # Performance tracking
        self.frame_count = 0
        self.fps = 0
        self.fps_start_time = time.time()
        self.last_frame_time = time.time()
        self.frame_scheduled = False
        self.target_fps = 24
        
        # Animation controls
        self.mix_ratio = 0.0
        self.rot = 0.0
        self.hue = 0.0
        self.sat = 1.0
        self.val = 1.0
        self.hsvToggle = 0.0
        
        # Start rendering
        self.after(100, self.redraw)
    
    def start_renderer_thread(self):
        """Start the renderer thread that will handle all OpenGL operations."""
        self.renderer_thread = threading.Thread(target=self.renderer_thread_func)
        self.renderer_thread.daemon = True
        self.renderer_thread.start()
    
    def renderer_thread_func(self):
        """Function that runs in the renderer thread.
        Creates a ModernGL context and processes render requests."""
        try:
            # Create the renderer
            self.renderer = OffscreenRenderer(self.width, self.height)
            
            # Mark as initialized
            self.gl_initialized = True
            
            # Process render requests until exit
            while not self.exit_flag.is_set():
                try:
                    # Get a command from the queue with a timeout
                    cmd, args, kwargs = self.render_queue.get(timeout=0.1)
                    
                    # Process the command
                    if cmd == 'render':
                        # Render a frame
                        result = self.renderer.render()
                        self.result_queue.put(('render_result', result))
                    elif cmd == 'update_texture':
                        # Update a texture
                        self.renderer.update_texture(*args, **kwargs)
                        self.result_queue.put(('texture_updated', True))
                    elif cmd == 'resize':
                        # Resize the framebuffer
                        self.renderer.set_size(*args)
                        self.result_queue.put(('resized', True))
                    elif cmd == 'set_uniform':
                        # Set a uniform value
                        name, value = args
                        setattr(self.renderer, name, value)
                        self.result_queue.put(('uniform_set', True))
                    elif cmd == 'set_shader':
                        # Set custom shader
                        vertex_source_or_file, fragment_source_or_file, is_file = args
                        self.set_shader(vertex_source_or_file, fragment_source_or_file, is_file)
                        self.result_queue.put(('shader_set', True))
                    elif cmd == 'add_method':
                        # Add a method to the renderer dynamically
                        method_name, method_func = args
                        import types
                        bound_method = types.MethodType(method_func, self.renderer)
                        setattr(self.renderer, method_name, bound_method)
                        self.result_queue.put(('method_added', True))
                    elif cmd == 'exit':
                        # Exit the thread
                        break
                    
                    # Mark task as done
                    self.render_queue.task_done()
                    
                except queue.Empty:
                    # No commands in queue, continue
                    pass
                except Exception as e:
                    # Log the error and continue
                    print(f"Error in renderer thread: {e}")
                    import traceback
                    traceback.print_exc()
        
        except Exception as e:
            # Log initialization error
            print(f"Error initializing renderer: {e}")
            import traceback
            traceback.print_exc()
        
        # Clean up
        if hasattr(self, 'renderer') and self.renderer:
            # Clean up OpenGL resources
            try:
                for texture in self.renderer.textures:
                    if texture:
                        texture.release()
                self.renderer.vao.release()
                self.renderer.vbo.release()
                self.renderer.ibo.release()
                self.renderer.prog.release()
                self.renderer.fbo.release()
            except:
                pass
    
    def update_fps_counter(self):
        """Update FPS counter and log the value."""
        # Increment frame counter
        self.frame_count += 1
        
        # Check if one second has elapsed
        current_time = time.time()
        elapsed = current_time - self.fps_start_time
        
        if elapsed >= 1.0:
            # Calculate FPS
            self.fps = self.frame_count / elapsed
            
            # Log FPS
            print(f"FPS: {self.fps:.1f}")
            
            # Reset counters
            self.frame_count = 0
            self.fps_start_time = current_time
    
    def set_initial_size(self, width, height):
        """Set the initial size of the frame before the first image is loaded."""
        self.width = width
        self.height = height
        self.canvas.config(width=width, height=height)
        self.update_idletasks()
        
        # Update renderer size
        if self.gl_initialized:
            self.render_queue.put(('resize', (width, height), {}))
    
    def redraw(self):
        """Request a new frame from the renderer and schedule the next redraw."""
        # Don't schedule if we're already waiting for a frame
        if self.frame_scheduled:
            return
            
        # Calculate frame timing for limiting
        current_time = time.time()
        
        # Calculate target frame duration (in seconds)
        target_duration = 1.0 / self.target_fps
        
        # Calculate how long since the last frame
        elapsed = current_time - self.last_frame_time
        
        # Calculate how long to wait to hit our target
        wait_time = target_duration - elapsed
        
        if wait_time > 0.001:  # Only wait if it's a meaningful amount of time (> 1ms)
            # Set flag to prevent double scheduling
            self.frame_scheduled = True
            
            # Schedule the actual redraw after waiting
            ms_wait = int(wait_time * 1000)  # Convert to milliseconds
            self.after(ms_wait, self._actual_redraw)
            return
        
        # If we don't need to wait, render immediately
        self._actual_redraw()
    
    def _actual_redraw(self):
        """The actual rendering code, separated to allow for frame timing."""
        # Clear scheduling flag
        self.frame_scheduled = False
        
        # Update last frame time
        self.last_frame_time = time.time()
        
        # Update FPS counter
        self.update_fps_counter()
        
        # Check if we have a renderer
        if not self.gl_initialized:
            # Try again later
            self.after(100, self.redraw)
            return
        
        # Forward uniforms to renderer
        self.render_queue.put(('set_uniform', ('mix_ratio', self.mix_ratio), {}))
        self.render_queue.put(('set_uniform', ('rot', self.rot), {}))
        self.render_queue.put(('set_uniform', ('hue', self.hue), {}))
        self.render_queue.put(('set_uniform', ('sat', self.sat), {}))
        self.render_queue.put(('set_uniform', ('val', self.val), {}))
        self.render_queue.put(('set_uniform', ('hsvToggle', self.hsvToggle), {}))
        
        # Request a new frame
        self.render_queue.put(('render', (), {}))
        
        # Process messages from the renderer
        self.process_renderer_messages()
        
        # Schedule next frame
        self.after(1, self.redraw)
    
    def process_renderer_messages(self):
        """Process any messages from the renderer thread."""
        try:
            # Check for render results
            while not self.result_queue.empty():
                msg_type, data = self.result_queue.get_nowait()
                
                if msg_type == 'render_result':
                    # Display the rendered image
                    self.display_image(data)
                
                # Mark as processed
                self.result_queue.task_done()
        except:
            pass
    
    def display_image(self, image):
        """Display an image on the canvas."""
        if not image:
            return
            
        # Convert to PhotoImage
        photo = ImageTk.PhotoImage(image)
        
        # Clear canvas
        self.canvas.delete("all")
        
        # Create new image on canvas
        self.canvas.create_image(0, 0, image=photo, anchor=tk.NW)
        
        # Keep a reference to prevent garbage collection
        self.canvas.photo = photo
    
    def GL_update_texture(self, image, texture_index=0):
        """Updates one of the textures with a new image."""
        if not self.gl_initialized:
            # Try again later
            self.after(100, lambda: self.GL_update_texture(image, texture_index))
            return
            
        if texture_index not in [0, 1]:
            raise ValueError("texture_index must be 0 or 1")
            
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Set image dimensions
        if texture_index == 0:
            self.image_width, self.image_height = image.size
            self.resize_to_image()
        
        # Forward to renderer thread
        self.render_queue.put(('update_texture', (image, texture_index), {}))
    
    def resize_to_image(self):
        """Resize the frame to match the image dimensions."""
        if hasattr(self, "image_width") and hasattr(self, "image_height"):
            # Update size
            self.width = self.image_width
            self.height = self.image_height
            
            # Update canvas size
            self.canvas.config(width=self.width, height=self.height)
            
            # Update renderer size
            if self.gl_initialized:
                self.render_queue.put(('resize', (self.width, self.height), {}))
            
            # Force the parent container to adapt to the new size
            self.update_idletasks()
    
    def set_mix_ratio(self, ratio):
        """Set the mix ratio between the two textures."""
        if ratio < -1.0 or ratio > 1.0:
            raise ValueError("Mix ratio must be between -1.0 and 1.0")
        self.mix_ratio = ratio
    
    def set_rotation(self, rotation):
        """Set the rotation value for the second texture."""
        self.rot = rotation
    
    def set_hue(self, hue):
        """Set the hue adjustment value."""
        self.hue = hue
    
    def set_saturation(self, saturation):
        """Set the saturation adjustment value."""
        self.sat = saturation
    
    def set_value(self, value):
        """Set the value/brightness adjustment value."""
        self.val = value
    
    def hsv_click(self, event=None):
        """Toggle HSV adjustment on/off."""
        if self.hsvToggle == 1.0:
            self.hsvToggle = 0.0
        else:
            self.hsvToggle = 1.0
    
    def set_shader(self, vertex_source_or_file="default.vert", fragment_source_or_file="default.frag", is_file=True):
        """Set custom shader code to be used for rendering.
        
        Args:
            vertex_source_or_file: Vertex shader source code or filename
            fragment_source_or_file: Fragment shader source code or filename
            is_file: If True, parameters are treated as filenames to load
        """
        # Store the last shader request to avoid duplicate scheduling
        vertex_source_or_file = f"assets/shaders/{vertex_source_or_file}"
        fragment_source_or_file = f"assets/shaders/{fragment_source_or_file}"
        self._last_shader_request = (vertex_source_or_file, fragment_source_or_file, is_file)
        
        if not self.gl_initialized:
            print("Cannot set shader - OpenGL not initialized")
            
            # Clear any existing scheduled calls with the same id
            if hasattr(self, '_shader_after_id') and self._shader_after_id:
                self.after_cancel(self._shader_after_id)
                
            # Schedule a new attempt and store the id
            self._shader_after_id = self.after(100, lambda: self.set_shader(
                *self._last_shader_request))
            return
        
        # Create command to set shader
        self.render_queue.put(('set_shader', 
                            (vertex_source_or_file, fragment_source_or_file, is_file), {}))
    
    def set_target_fps(self, fps):
        """Set the target frame rate."""
        self.target_fps = max(1, min(60, fps))
    
    def cleanup(self):
        """Clean up resources before destruction."""
        # Signal the renderer thread to exit
        self.exit_flag.set()
        self.render_queue.put(('exit', (), {}))
        
        # Wait for the thread to finish (with timeout)
        if hasattr(self, 'renderer_thread') and self.renderer_thread.is_alive():
            self.renderer_thread.join(timeout=1.0)
