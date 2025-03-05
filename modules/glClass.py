from OpenGL.GL import *
from OpenGL.GL import shaders
from pyopengltk import OpenGLFrame
import platform
import ctypes
from OpenGL import platform as oglplatform

class AppOgl(OpenGLFrame):
    def initgl(self):
        """Initialize OpenGL settings and create a texture."""
        glViewport(0, 0, self.width, self.height)
        glClearColor(0.0, 0.0, 0.0, 1.0)

        # Create and compile shaders
        self.init_shaders()

        # Generate two empty OpenGL textures
        self.texture_ids = glGenTextures(2)
        self.texture_id = self.texture_ids[0]  # For backward compatibility
        
        # Setup first texture
        glBindTexture(GL_TEXTURE_2D, self.texture_ids[0])
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        
        # Setup second texture
        glBindTexture(GL_TEXTURE_2D, self.texture_ids[1])
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        glEnable(GL_TEXTURE_2D)
        
        # Set up FPS counter
        self.setup_fps_counter()
        
        # Try to set animation rate through pyopengltk
        # This is a common approach in Tkinter-based OpenGL frames
        if hasattr(self, 'setAnimationRate'):
            # If the method exists, use it (30ms interval ≈ 33 FPS)
            self.setAnimationRate(30)
            print("Set animation rate to 30ms")
            
        # Alternatively, check if we can modify the animationRate attribute directly
        elif hasattr(self, 'animationRate'):
            self.animationRate = 30  # ms between frames
            print("Set animation rate attribute to 30ms")
        
        # Create and bind VAO and VBO for rendering quad
        self.setup_quad()

        # Wait here until OpenGL is fully initialized
        self.gl_initialized = False

        def wait_for_gl():
            self.update_idletasks()  # Process pending events
            if hasattr(self, "texture_id") and hasattr(self, "shader_program"):
                self.gl_initialized = True
            else:
                self.after(10, wait_for_gl)  # Retry in 10ms

        wait_for_gl()
    
    def setup_fps_counter(self):
        """Initialize FPS counter variables."""
        import time
        self.frame_count = 0
        self.fps = 0
        self.fps_start_time = time.time()
        self.last_frame_time = time.time()  # For frame limiting
    
    def init_shaders(self):
        """Initialize vertex and fragment shaders using default built-in shaders."""
        # Default vertex shader for a simple textured quad
        default_vertex_shader = """
        #version 330 core
        layout(location = 0) in vec3 position;
        layout(location = 1) in vec2 texCoord;
        
        out vec2 TexCoord;
        
        void main() {
            gl_Position = vec4(position, 1.0);
            TexCoord = texCoord;
        }
        """
        
        # Default fragment shader with two texture inputs
        default_fragment_shader = """
        #version 330 core
        in vec2 TexCoord;
        
        uniform sampler2D textureSampler1;  // First texture
        uniform sampler2D textureSampler2;  // Second texture
        uniform float time;                 // For animated effects
        uniform float mixRatio;             // Blend ratio between textures
        
        out vec4 FragColor;
        
        void main() {
            // Sample both textures
            vec4 texColor1 = texture(textureSampler1, TexCoord);
            vec4 texColor2 = texture(textureSampler2, TexCoord);
            
            // Animated mix ratio (can be overridden by uniform)
            float animatedMix = (sin(time) + 1.0) / 2.0;
            float currentMix = mixRatio > 0.0 ? mixRatio : animatedMix;
            
            // Blend the two textures
            vec4 blendedColor = mix(texColor1, texColor2, currentMix);
            
            // Example effect: Vignette
            vec2 center = vec2(0.5, 0.5);
            float dist = distance(TexCoord, center);
            float vignette = smoothstep(0.5, 0.2, dist);
            
            // Apply vignette
            vec3 finalColor = blendedColor.rgb * vignette;
            
            FragColor = vec4(finalColor, blendedColor.a);
        }
        """
        
        # Try to load shaders from files, fall back to defaults if not found
        try:
            vertex_shader_source = self.load_shader_file("default.vert", default_vertex_shader)
            fragment_shader_source = self.load_shader_file("default.frag", default_fragment_shader)
            
            # Compile shaders
            vertex = shaders.compileShader(vertex_shader_source, GL_VERTEX_SHADER)
            fragment = shaders.compileShader(fragment_shader_source, GL_FRAGMENT_SHADER)
            
            print("Loaded default shaders")
        except Exception as e:
            print(f"Error loading default shaders, using built-in defaults: {e}")
            
            # Compile default shaders
            vertex = shaders.compileShader(default_vertex_shader, GL_VERTEX_SHADER)
            fragment = shaders.compileShader(default_fragment_shader, GL_FRAGMENT_SHADER)
        
        # Link shaders into a program
        self.shader_program = shaders.compileProgram(vertex, fragment)
        
        # Get uniform locations
        self.texture_uniform1 = glGetUniformLocation(self.shader_program, "textureSampler1")
        self.texture_uniform2 = glGetUniformLocation(self.shader_program, "textureSampler2")
        self.time_uniform = glGetUniformLocation(self.shader_program, "time")
        self.mix_ratio_uniform = glGetUniformLocation(self.shader_program, "mixRatio")
        self.rotation_uniform = glGetUniformLocation(self.shader_program, "rot")
        self.hue_uniform = glGetUniformLocation(self.shader_program, "hue")
        self.saturation_uniform = glGetUniformLocation(self.shader_program, "sat")
        self.value_uniform = glGetUniformLocation(self.shader_program, "val")
        self.hsvToggle_uniform = glGetUniformLocation(self.shader_program, "hsvToggle")
        
        # Initialize mix ratio
        self.mix_ratio = 0.0  # Negative means use animated mix
        self.rot = 0.0
        self.hue = 0.0
        self.sat = 1.0
        self.val = 1.0
        self.hsvToggle = 0.0

        
        # Initialize time variable for animation
        self.start_time = 0
        self.current_time = 0
    
    def setup_quad(self):
        """Create vertex array and buffers for a full-screen quad."""
        # Vertex data for a quad (x, y, z, tx, ty)
        quad_vertices = [
            # Position (x, y, z)    # Texture coords (tx, ty)
            -1.0, -1.0, 0.0,        0.0, 0.0,  # Bottom-left
             1.0, -1.0, 0.0,        1.0, 0.0,  # Bottom-right
             1.0,  1.0, 0.0,        1.0, 1.0,  # Top-right
            -1.0,  1.0, 0.0,        0.0, 1.0   # Top-left
        ]
        
        # Indices for two triangles
        quad_indices = [
            0, 1, 2,  # First triangle
            0, 2, 3   # Second triangle
        ]
        
        # Convert to numpy arrays of correct type
        import numpy as np
        quad_vertices = np.array(quad_vertices, dtype=np.float32)
        quad_indices = np.array(quad_indices, dtype=np.uint32)
        
        # Create and bind the Vertex Array Object
        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)
        
        # Create and bind the Vertex Buffer Object
        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, quad_vertices.nbytes, quad_vertices, GL_STATIC_DRAW)
        
        # Create and bind the Element Buffer Object
        self.ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, quad_indices.nbytes, quad_indices, GL_STATIC_DRAW)
        
        # Position attribute (3 floats)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 5 * np.float32().nbytes, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        
        # Texture coordinate attribute (2 floats)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 5 * np.float32().nbytes, 
                            ctypes.c_void_p(3 * np.float32().nbytes))
        glEnableVertexAttribArray(1)
        
        # Unbind the VAO
        glBindVertexArray(0)

    def update_fps_counter(self):
        """Update FPS counter and log the value."""
        import time
        
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

    def setup_fps_counter(self):
        """Initialize FPS counter variables with frame limiter."""
        import time
        self.frame_count = 0
        self.fps = 0
        self.fps_start_time = time.time()
        self.last_frame_time = time.time()
        self.frame_scheduled = False  # Flag to prevent double scheduling
        self.target_fps = 24  # Target frame rate (matches your 1.0/24.0 setting)

    def redraw(self):
        """Render a textured quad using shaders with frame limiting."""
        import time
        
        # Prevent multiple scheduling
        if hasattr(self, 'frame_scheduled') and self.frame_scheduled:
            return
            
        # Calculate frame timing for limiting
        current_time = time.time()
        
        if hasattr(self, 'last_frame_time'):
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
        import time
        
        # Clear scheduling flag
        self.frame_scheduled = False
        
        # Update last frame time
        self.last_frame_time = time.time()
        
        # Update FPS counter
        self.update_fps_counter()
        
        # Clear the screen
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # Rest of your rendering code...
        # Use shader program
        glUseProgram(self.shader_program)
        
        # Update time uniform for animations
        if not hasattr(self, "start_time") or self.start_time == 0:
            self.start_time = time.time()
        self.current_time = time.time() - self.start_time
        glUniform1f(self.time_uniform, self.current_time)
        
        # Bind the first texture to texture unit 0
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.texture_ids[0])
        glUniform1i(self.texture_uniform1, 0)
        
        # Bind the second texture to texture unit 1
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, self.texture_ids[1])
        glUniform1i(self.texture_uniform2, 1)
        
        # Set mix ratio uniform
        glUniform1f(self.mix_ratio_uniform, self.mix_ratio)
        glUniform1f(self.rotation_uniform, self.rot)
        glUniform1f(self.hue_uniform, self.hue)
        glUniform1f(self.saturation_uniform, self.sat)
        glUniform1f(self.value_uniform, self.val)
        glUniform1f(self.hsvToggle_uniform, self.hsvToggle)
        
        # Bind vertex array and draw
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        
        # Unbind shader program
        glUseProgram(0)

    # This method needs to be modified to avoid direct redraw calls
    def GL_update_texture(self, image, texture_index=0):
        """Updates one of the OpenGL textures with a new image."""
        if texture_index not in [0, 1]:
            raise ValueError("texture_index must be 0 or 1")
            
        image = image.convert("RGB")
        
        # Set image dimensions from the first texture
        if texture_index == 0:
            self.image_width, self.image_height = image.size
            # Resize the frame to match the image dimensions
            self.resize_to_image()
        
        # Convert image to raw bytes
        image_data = image.tobytes("raw", "RGB", 0, -1)
        
        # Bind and update the specified OpenGL texture
        glBindTexture(GL_TEXTURE_2D, self.texture_ids[texture_index])
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, image.width, image.height,
                    0, GL_RGB, GL_UNSIGNED_BYTE, image_data)

    def resize_to_image(self):
        """Resize the OpenGL frame to match the image dimensions."""
        if hasattr(self, "image_width") and hasattr(self, "image_height"):
            # Update the frame's size
            self.config(width=self.image_width, height=self.image_height)
            
            # Update OpenGL viewport to match new dimensions
            glViewport(0, 0, self.image_width, self.image_height)
            
            # Force the parent container to adapt to the new size if needed
            self.update_idletasks()

    def set_initial_size(self, width, height):
        """Set the initial size of the OpenGL frame before the first image is loaded.
        This helps prevent flickering by pre-allocating space."""
        self.image_width = width
        self.image_height = height
        self.config(width=width, height=height)

        # Wait here until OpenGL is fully initialized
        self.gl_initialized = False

        def wait_for_gl():
            self.update_idletasks()  # Process pending events
            if hasattr(self, "texture_id") and hasattr(self, "shader_program"):
                self.gl_initialized = True
            else:
                self.after(10, wait_for_gl)  # Retry in 10ms

        wait_for_gl()

        # Update OpenGL viewport to match dimensions
        glViewport(0, 0, width, height)
        
    def load_shader_file(self, filename, default_content=None):
        """Load shader source from a file.
        
        Args:
            filename: Path to shader file
            default_content: Default content to use if file can't be loaded
            
        Returns:
            String containing shader source code
        """

        filename = f"assets/shaders/{filename}"
        print(f"Loading shader file: {filename}")
        try:
            with open(filename, 'r') as f:
                return f.read()
        except (IOError, FileNotFoundError) as e:
            if default_content is not None:
                print(f"Could not load shader file '{filename}', using default: {e}")
                return default_content
            else:
                raise RuntimeError(f"Could not load shader file '{filename}'") from e
    
    def set_shader(self, vertex_source_or_file, fragment_source_or_file, is_file=False):
        """Set custom shader code to be used for rendering.
        
        Args:
            vertex_source_or_file: Vertex shader source code or filename
            fragment_source_or_file: Fragment shader source code or filename
            is_file: If True, parameters are treated as filenames to load
        """
        # Delete old shader program if it exists
        if hasattr(self, "shader_program"):
            glDeleteProgram(self.shader_program)
        
        try:
            # Load shader source from files if requested
            if is_file:
                vertex_shader_source = self.load_shader_file(vertex_source_or_file)
                fragment_shader_source = self.load_shader_file(fragment_source_or_file)
                print(f"Loaded shaders from files: {vertex_source_or_file}, {fragment_source_or_file}")
            else:
                vertex_shader_source = vertex_source_or_file
                fragment_shader_source = fragment_source_or_file
            
            # Compile new shaders
            vertex = shaders.compileShader(vertex_shader_source, GL_VERTEX_SHADER)
            fragment = shaders.compileShader(fragment_shader_source, GL_FRAGMENT_SHADER)
            
            # Link shaders into a program
            self.shader_program = shaders.compileProgram(vertex, fragment)
            
            # Get uniform locations
            self.texture_uniform1 = glGetUniformLocation(self.shader_program, "textureSampler1")
            self.texture_uniform2 = glGetUniformLocation(self.shader_program, "textureSampler2")
            self.time_uniform = glGetUniformLocation(self.shader_program, "time")
            self.mix_ratio_uniform = glGetUniformLocation(self.shader_program, "mixRatio")
            
            # Reset animation timer
            self.start_time = 0
            
            # Force redraw
            self.redraw()
            
        except Exception as e:
            # Log error details for debugging
            print(f"Error setting shader: {e}")
            import traceback
            traceback.print_exc()
            raise
        
    def set_mix_ratio(self, ratio):
        """Set the mix ratio between the two textures.
        
        Args:
            ratio: Float between 0.0 and 1.0, or -1.0 for animated mixing
                  0.0 = 100% texture1, 1.0 = 100% texture2
        """
        if ratio < -1.0 or ratio > 1.0:
            raise ValueError("Mix ratio must be between -1.0 and 1.0")
            
        self.mix_ratio = ratio

    def set_rotation(self, rotation):
        self.rot = rotation
    
    def set_hue(self, hue):
        self.hue = hue

    def set_saturation(self, saturation):
        self.sat = saturation
    
    def set_value(self, value):
        self.val = value

    def hsv_click(self, event=None):
        if self.hsvToggle == 1.0:
            self.hsvToggle = 0.0
        else:
            self.hsvToggle = 1.0
