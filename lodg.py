import multiprocessing as mp
from pathlib import Path
import numpy as np
from PIL import Image
from es3 import nif
from es3.utils import meshoptimizer

class VFSLODGenerator:
    def __init__(self, data_paths, output_folder, allowed_folders=None, debug_mode=False):
        """
        Initialize LOD Generator with virtual file system support.
        
        Args:
            data_paths (list): List of data paths in order of precedence (last one wins)
            output_folder (str/Path): Folder where LOD files will be saved
            allowed_folders (list): List of folder names under meshes/ to process
            debug_mode (bool): Enable debug visualization of LOD levels
        """
        self.data_paths = [Path(p) for p in data_paths]
        self.output_folder = Path(output_folder)
        self.allowed_folders = set(allowed_folders) if allowed_folders else None
        self.texture_extensions = ['.dds', '.tga', '.png', '.bmp']
        self.debug_mode = debug_mode

    def is_allowed_path(self, path):
        """
        Check if the given path is in one of the allowed folders.
        
        Args:
            path (Path): Path to check
            
        Returns:
            bool: True if path is allowed, False otherwise
        """
        if not self.allowed_folders:
            return True
            
        # Get the first folder after 'meshes' in the path
        parts = path.parts
        try:
            meshes_index = parts.index('meshes')
            if len(parts) > meshes_index + 1:
                first_folder = parts[meshes_index + 1]
                return first_folder.lower() in self.allowed_folders
        except ValueError:
            pass
        return False
        
    def find_file(self, relative_path, subdirs=None):
        """
        Find a file in the virtual file system.
        
        Args:
            relative_path (str/Path): Relative path to search for
            subdirs (list): Optional list of subdirectories to check in each data path
            
        Returns:
            Path or None: Full path to found file, or None if not found
        """
        relative_path = Path(relative_path)
        
        # Search paths in reverse order (last one wins)
        for data_path in reversed(self.data_paths):
            if subdirs:
                for subdir in subdirs:
                    full_path = data_path / subdir / relative_path
                    if full_path.exists():
                        return full_path
            else:
                full_path = data_path / relative_path
                if full_path.exists():
                    return full_path
        return None

    def determine_lod_level(self, radius):
        """Determine appropriate LOD distance level based on mesh radius"""
        if radius < 100:
            return 0
        elif radius < 200:
            return 1
        elif radius < 500:
            return 2
        elif radius < 1000:
            return 3
        elif radius < 1800:
            return 4
        else:
            return 5

    def find_texture_file(self, texture_path):
        """
        Find texture in VFS with improved logging and DDS-only search.
        
        Args:
            texture_path (str/Path): Path to texture file
                
        Returns:
            Path or None: Full path to found texture file, or None if not found
        """
        texture_path = Path(texture_path)
        
        # Ensure path starts with textures/
        if not str(texture_path).lower().startswith('textures'):
            texture_path = Path('textures') / texture_path
                    
        base_path = texture_path.with_suffix('')  # Remove extension if present
        
        # Log the base path we're searching for
        #print(f"\nSearching for texture: {base_path}")
        
        # Try DDS extension only
        target_path = f"{base_path}.dds"
        #print(f"\nTrying variations of: {target_path}")
        
        # Search paths in reverse order (last one wins)
        for data_path in reversed(self.data_paths):
            # Try with textures/ prefix
            full_path = data_path / target_path
            #print(f"Checking: {full_path}")
            if full_path.exists():
                #print(f"Found at: {full_path}")
                return full_path
                        
        print(f"\nTexture not found: {texture_path}")
        return None
        
    def load_texture(self, texture_filename):
        """Load and normalize texture from VFS"""
        try:
            texture_path = self.find_texture_file(texture_filename)
            if texture_path is None:
                print(f"Texture not found in VFS: {texture_filename} (tried extensions: {self.texture_extensions})")
                return None
                
            img = Image.open(texture_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            return np.array(img) / 255.0
        except Exception as e:
            print(f"Texture load error: {texture_filename} - {e}")
            return None

    def sample_texture(self, texture, uv_coords):
        """Sample texture at given UV coordinates"""
        h, w = texture.shape[:2]
        u, v = uv_coords
        
        u = u % 1.0
        v = v % 1.0
        
        px = int(u * (w - 1))
        py = int((1 - v) * (h - 1))
        
        return texture[py, px]

    def get_output_path(self, input_path, lod_level):
        """Generate output path for LOD file"""
        input_path = Path(input_path)
        
        # Extract the part of the path after 'meshes'
        parts = input_path.parts
        try:
            meshes_index = parts.index('meshes')
            relative_parts = parts[meshes_index+1:]
            relative_path = Path(*relative_parts)
        except ValueError:
            # If 'meshes' not found, use the filename only
            relative_path = input_path.name
            
        filename = relative_path.stem
        suffix = f'_dist_{lod_level}'
        new_filename = f"{filename}{suffix}{relative_path.suffix}"
        
        # Use specified output folder while maintaining subfolder structure
        output_path = self.output_folder / relative_path.parent / new_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        return output_path

    def optimize_and_save_mesh(self, stream, output_path, data, vertex_precision=0.001):
        """
        Optimizes and saves a mesh with improved vertex cache efficiency and data deduplication.
        
        Args:
            stream (NiStream): The NIF stream containing the mesh data
            output_path (Path): Output path for the optimized mesh
            data (NiTriShapeData): The mesh data to optimize
            vertex_precision (float): Precision for vertex deduplication
        """
        if len(data.vertices) == 0:
            return
            
        # Step 1: Clear duplicates by combining vertex attributes
        if len(data.vertices):
            vertex_data = [data.vertices]
            
            if len(data.normals):
                vertex_data.append(data.normals)
                
            if len(data.vertex_colors):
                vertex_data.append(data.vertex_colors)
                
            if len(data.uv_sets):
                vertex_data.extend(data.uv_sets)
                
            # Find unique vertex combinations based on all attributes
            unique_indices, inverse = self.unique_rows(vertex_data, precision=vertex_precision)
            
            if unique_indices is not None:
                # Update triangles to use the remapped indices
                original_triangles = data.triangles.copy()
                data.triangles = inverse[original_triangles]
                
                # Update vertex attributes using unique indices
                if len(data.vertices):
                    data.vertices = data.vertices[unique_indices]
                if len(data.normals):
                    data.normals = data.normals[unique_indices]
                if len(data.vertex_colors):
                    data.vertex_colors = data.vertex_colors[unique_indices]
                if len(data.uv_sets):
                    data.uv_sets = data.uv_sets[:, unique_indices]

        # Step 2: Apply the vertex cache optimization
        if len(data.triangles):
            try:
                vertex_remap, triangles = meshoptimizer.optimize(
                    data.vertices, 
                    data.triangles.astype(np.uint32)
                )
                data.triangles = triangles.astype(np.uint16)
                
                # Remap all vertex attributes
                if len(data.vertices):
                    data.vertices[vertex_remap] = data.vertices.copy()
                if len(data.normals):
                    data.normals[vertex_remap] = data.normals.copy()
                if len(data.vertex_colors):
                    data.vertex_colors[vertex_remap] = data.vertex_colors.copy()
                if len(data.uv_sets):
                    data.uv_sets[:, vertex_remap] = data.uv_sets.copy()
            except Exception as e:
                print(f"Warning: Vertex cache optimization failed: {e}")

        # Step 3: Update center and radius
        data.update_center_radius()
        
        # Step 4: Sort and optimize properties
        # Merge duplicate properties
        stream.merge_properties(ignore={"name", "shine", "specular_color"})
        stream.sort()
        
        # Step 5: Save optimized mesh
        stream.save(output_path)

    def unique_rows(self, arrays, precision=0.001):
        """
        Find unique rows across multiple arrays considering numerical precision.
        
        Args:
            arrays (list): List of numpy arrays to check for uniqueness
            precision (float): Precision for floating point comparison
            
        Returns:
            tuple: (unique indices, inverse mapping)
        """
        if not arrays:
            return None, None
            
        try:
            # Scale up the values to convert floats to ints for exact comparison
            scale = round(1 / precision)
            scaled = [(arr * scale).round().astype(np.int64) for arr in arrays]
            
            # Combine all arrays into a structured array for comparison
            dtype = [(f'f{i}', arr.dtype, arr.shape[1:]) for i, arr in enumerate(scaled)]
            combined = np.empty(len(scaled[0]), dtype=dtype)
            
            for i, arr in enumerate(scaled):
                combined[f'f{i}'] = arr
                
            # Find unique rows
            _, idx, inv = np.unique(combined, return_index=True, return_inverse=True)
            
            # Sort indices to maintain original order
            idx.sort()
            
            return idx, inv
        except Exception as e:
            print(f"Warning: Vertex deduplication failed: {e}")
            return None, None

    def merge_identical_shapes(self, stream):
        """
        Merges NiTriShapes that have identical properties but different geometry data.
        Skips any shapes that have textures since those are handled by texture baking.
        
        Args:
            stream (NiStream): The NIF stream to optimize
        """
        def find_parent_node(stream, shape):
            """Find the parent NiNode for a given shape"""
            for node in stream.objects_of_type(nif.NiNode):
                if shape in node.children:
                    return node
            return None

        def has_texturing_property(shape):
            """Check if shape has a NiTexturingProperty"""
            return any(isinstance(p, nif.NiTexturingProperty) for p in shape.properties)

        def are_properties_identical(props1, props2):
            """Compare two sets of properties for equality"""
            if len(props1) != len(props2):
                return False
            
            for p1, p2 in zip(props1, props2):
                if type(p1) != type(p2):
                    return False
                    
                # Compare relevant attributes based on property type
                if isinstance(p1, nif.NiMaterialProperty):
                    # Compare material colors and values
                    attrs_to_check = [
                        'ambient_color', 'diffuse_color', 'specular_color', 
                        'emissive_color', 'shine', 'alpha'
                    ]
                    for attr in attrs_to_check:
                        if not np.array_equal(getattr(p1, attr), getattr(p2, attr)):
                            return False
                            
                elif isinstance(p1, nif.NiAlphaProperty):
                    # Compare alpha property settings
                    if p1.alpha_blending != p2.alpha_blending or \
                    p1.alpha_testing != p2.alpha_testing or \
                    p1.test_ref != p2.test_ref or \
                    p1.test_mode != p2.test_mode or \
                    p1.src_blend_mode != p2.src_blend_mode or \
                    p1.dst_blend_mode != p2.dst_blend_mode:
                        return False
                        
                elif isinstance(p1, nif.NiStencilProperty):
                    if p1.draw_mode != p2.draw_mode:
                        return False
                        
                elif isinstance(p1, nif.NiWireframeProperty):
                    if p1.wireframe != p2.wireframe:
                        return False
                        
                else:
                    print(f"Warning: Unhandled property type for comparison: {type(p1)}")
                    return False
                    
            return True

        def merge_geometry(shapes):
            """Merge geometry data from multiple shapes into one"""
            base_shape = shapes[0]
            base_data = base_shape.data
            
            # Calculate total sizes
            total_vertices = sum(shape.data.vertices.shape[0] for shape in shapes)
            total_triangles = sum(shape.data.triangles.shape[0] for shape in shapes)
            
            # Create new merged data
            merged_data = nif.NiTriShapeData()
            merged_data.vertices = np.zeros((total_vertices, 3), dtype=base_data.vertices.dtype)
            merged_data.triangles = np.zeros((total_triangles, 3), dtype=base_data.triangles.dtype)
            
            # Initialize other arrays if they exist in base data
            if len(base_data.normals):
                merged_data.normals = np.zeros((total_vertices, base_data.normals.shape[1]), dtype=base_data.normals.dtype)
            if len(base_data.vertex_colors):
                # Create empty array with correct shape
                vc_shape = base_data.vertex_colors.shape
                if len(vc_shape) == 2:  # Check if shape is 2D
                    color_components = vc_shape[1]  # Get number of color components (3 for RGB, 4 for RGBA)
                    merged_data.vertex_colors = np.zeros((total_vertices, color_components), dtype=base_data.vertex_colors.dtype)
                else:
                    print(f"Warning: Unexpected vertex color shape: {vc_shape}")
                    # Create empty vertex colors array instead of None
                    merged_data.vertex_colors = np.zeros((0, 4), dtype=np.float32)
            
            # Copy data from each shape
            vertex_offset = 0
            triangle_offset = 0
            
            for shape in shapes:
                data = shape.data
                num_verts = len(data.vertices)
                num_tris = len(data.triangles)
                
                # Copy vertices
                merged_data.vertices[vertex_offset:vertex_offset + num_verts] = data.vertices
                
                # Copy triangles with offset
                merged_data.triangles[triangle_offset:triangle_offset + num_tris] = \
                    data.triangles + vertex_offset
                
                # Copy other attributes if they exist
                if len(data.normals):
                    merged_data.normals[vertex_offset:vertex_offset + num_verts] = data.normals
                if hasattr(merged_data, 'vertex_colors') and len(data.vertex_colors):
                    try:
                        merged_data.vertex_colors[vertex_offset:vertex_offset + num_verts] = data.vertex_colors
                    except ValueError as e:
                        print(f"Warning: Could not copy vertex colors - shape mismatch. Source: {data.vertex_colors.shape}, Target: {merged_data.vertex_colors.shape}")
                        # Create empty vertex colors array instead of None
                        merged_data.vertex_colors = np.zeros((0, 4), dtype=np.float32)
                
                vertex_offset += num_verts
                triangle_offset += num_tris
            
            # Update center and radius
            merged_data.update_center_radius()
            return merged_data

        # Find all NiTriShapes
        shapes = [shape for shape in stream.objects_of_type(nif.NiTriShape) 
                if not has_texturing_property(shape)]  # Skip textured shapes
        
        if not shapes:
            return

        # Group shapes by their property sets
        shape_groups = {}
        for shape in shapes:
            # Create a property tuple key
            prop_key = tuple(type(p) for p in shape.properties)
            
            # Skip shapes with different property types
            if not prop_key:
                continue
                
            # Find matching group or create new one
            found = False
            for key, group in shape_groups.items():
                if prop_key == key and are_properties_identical(shape.properties, group[0].properties):
                    group.append(shape)
                    found = True
                    break
                    
            if not found:
                shape_groups[prop_key] = [shape]

        # Merge shapes within each group
        for group in shape_groups.values():
            if len(group) < 2:
                continue
                
            print(f"Merging group of {len(group)} non-textured shapes with identical properties")
                
            # Merge geometry of all shapes in group
            merged_data = merge_geometry(group)
            
            # Use first shape as the merged shape
            merged_shape = group[0]
            merged_shape.data = merged_data
            
            # Remove other shapes from their parents
            for shape in group[1:]:
                parent_node = find_parent_node(stream, shape)
                if parent_node:
                    # Remove shape from parent's children
                    if shape in parent_node.children:
                        parent_node.children.remove(shape)
                        
                # Break references to the shape's data and properties
                shape.data = None
                shape.properties = []  # Empty list instead of None entries
                
                # Remove shape from parent's children
                parent_node = find_parent_node(stream, shape)
                if parent_node:
                    if shape in parent_node.children:
                        parent_node.children = [child for child in parent_node.children if child is not shape]
                
                # If shape is in root, remove it
                if shape in stream.roots:
                    stream.roots = [root for root in stream.roots if root is not shape]
                    
        # Clean up None properties from any remaining shapes
        for shape in stream.objects_of_type(nif.NiTriShape):
            shape.properties = [p for p in shape.properties if p is not None]
        
        # Merge identical properties to clean up unreferenced properties
        stream.merge_properties(ignore={"name", "shine", "specular_color"})
        
        # Sort to clean up the stream
        stream.sort()

    def process_mesh(self, filepath):
        """Process a single mesh file"""
        try:
            stream = nif.NiStream()
            stream.load(filepath)

            modified = False
            for geom in stream.objects_of_type(nif.NiTriShape):
                data = geom.data
                
                if not hasattr(data, 'uv_sets') or len(data.uv_sets) == 0:
                    #print(f"Warning: Skipping {filepath} - mesh has no UV mapping data (required for texture baking)")
                    continue

                # Check for NiAlphaProperty - if present, skip this mesh
                has_alpha_property = any(isinstance(p, nif.NiAlphaProperty) for p in geom.properties)
                if has_alpha_property:
                    #print(f"Skipping {filepath} - mesh has NiAlphaProperty (preserving texture for transparency)")
                    continue

                lod_level = self.determine_lod_level(data.radius)
                
                tex_prop = next((p for p in geom.properties if isinstance(p, nif.NiTexturingProperty)), None)
                if tex_prop is None or not hasattr(tex_prop, 'base_texture') or tex_prop.base_texture is None:
                    #print(f"No texture property in {filepath}")
                    continue

                texture_filename = tex_prop.base_texture.source.filename
                texture = self.load_texture(texture_filename)
                if texture is None:
                    continue

                if not hasattr(data, 'vertex_colors') or data.vertex_colors is None or len(data.vertex_colors) == 0:
                    # Initialize vertex colors array with correct size
                    vertex_count = len(data.vertices)
                    data.vertex_colors = np.ones((vertex_count, 4), dtype=np.float32)
                    data.vertex_colors[:, 3] = 1.0  # Set alpha to 1.0

                # Validate vertex colors array size matches vertices
                if len(data.vertex_colors) != len(data.vertices):
                    print(f"Warning: Vertex color count mismatch in {filepath} - reinitializing")
                    data.vertex_colors = np.ones((len(data.vertices), 4), dtype=np.float32)
                    data.vertex_colors[:, 3] = 1.0  # Set alpha to 1.0

                # Scale texture based on LOD level
                texture_height, texture_width = texture.shape[:2]
                scale_factor = 2 ** (2 + lod_level)
                scaled_height = max(1, texture_height // scale_factor)
                scaled_width = max(1, texture_width // scale_factor)
                
                texture_pil = Image.fromarray((texture * 255).astype(np.uint8))
                scaled_texture = np.array(texture_pil.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)) / 255.0

                for i, uv in enumerate(data.uv_sets[0]):
                    sampled_color = self.sample_texture(scaled_texture, uv)
                    data.vertex_colors[i, :3] = data.vertex_colors[i, :3] * sampled_color

                if self.debug_mode:
                    # Debug tints for different LOD levels
                    tints = [
                        [1.6, 2.2, 2.2],  # Magenta (level 0)
                        [1.6, 2.2, 2.2],  # Yellow (level 1)
                        [1.6, 2.2, 2.2],  # Cyan (level 2)
                        [1.6, 2.2, 2.2],  # Red (level 3)
                        [1.6, 2.2, 2.2],  # Red (level 4)
                        [1.6, 2.2, 2.2],  # Red (level 5)


                    ]
                    tint = np.array(tints[lod_level])
                    data.vertex_colors[:, :3] *= tint

                geom.properties = [p for p in geom.properties if not isinstance(p, nif.NiTexturingProperty)]
                modified = True

            if modified:
                output_path = self.get_output_path(filepath, lod_level)

                # Merge identical shapes
                self.merge_identical_shapes(stream)

                self.optimize_and_save_mesh(stream, output_path, data)
                print(f"Successfully processed: {filepath} -> {output_path} (LOD level {lod_level}, radius: {data.radius:.2f})")
                return True
            else:
                #print(f"No modifications needed for: {filepath}")
                return False

        except Exception as e:
            print(f"Processing error for {filepath}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def find_all_meshes(self):
        """Find all mesh files in VFS within allowed folders"""
        mesh_files = set()
        for data_path in self.data_paths:
            mesh_path = data_path / "meshes"
            if mesh_path.exists():
                for file in mesh_path.rglob("*.[nN][iI][fF]"):
                    if self.is_allowed_path(file):
                        mesh_files.add(file)
        return sorted(list(mesh_files))

    def process_all(self):
        """Process all meshes found in VFS"""
        files = self.find_all_meshes()
        print(f"Found {len(files)} files to process in VFS")
        
        with mp.Pool() as executor:
            results = executor.map(self.process_mesh, files)
        
        successful = sum(1 for r in results if r)
        print(f"Processed {successful} of {len(files)} files successfully")

def main():
    # Example data paths in order of precedence
    data_paths = [
        "C:/openmwassets/ogmeshes",
        "C:/openmwassets/met",
        "C:/mgem/Morrowindex/Data Files",
        "C:/openmwassets/mop",
        "C:/openmwassets/sponzapbr",
        "C:/openmwassets/axepbr",
        "C:/openmwassets/fx",
        "C:/openmwassets/cavernspbr",
        "C:/openmwassets/townspbr",
        "C:/openmwassets/trdata",
        "C:/openmwassets/oaab",
        "C:/openmwassets/remirosgrass",
        "C:/openmwassets/remirostest",
        "C:/openmwassets/balmora",
        "C:/openmwassets/vivec",
        "C:/openmwassets/betterfx",
        "C:/openmwassets/cinematic",
        "C:/openmwassets/cavespbr",
        "C:/openmwassets/rocky",
        "C:/openmwassets/trans",
        "C:/openmwassets/vivecpbr",
        "C:/openmwassets/steel",
        "C:/openmwassets/attack",
        "C:/openmwassets/gitd",
        "C:/openmwassets/mopvfx",
        "C:/projects/texturematcher/staging/openmwassets"
    ]
    
    # Specify custom output folder for LOD files
    output_folder = "C:/openmwassets/lod/meshes"

    # Specify allowed folders (case-insensitive)
    allowed_folders = {'x', 'f', 'd', 'l'}
    
    generator = VFSLODGenerator(data_paths, output_folder, allowed_folders=allowed_folders, debug_mode=True)
    generator.process_all()

if __name__ == "__main__":
    from timeit import default_timer
    
    time = default_timer()
    main()
    time = default_timer() - time
    print(f"Finished: {time:.4f} seconds")