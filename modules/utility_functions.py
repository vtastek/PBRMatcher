import os
import time
import sys


# Global dictionary to track start times of functions
start_times = {}

# Stack to keep track of function call hierarchy
call_stack = []

# Threshold for long-running functions (in seconds)
LONG_FUNCTION_THRESHOLD = 0.004

# Boolean flag to toggle the logging behavior
log_long_functions = True  # Set this to False to log all function calls

def log_function_calls(frame, event, arg):
    if event == "call":
        func_name = frame.f_code.co_name
        func_file = frame.f_code.co_filename
        func_line = frame.f_lineno
        print(f"Function {func_name} called in {func_file}:{func_line}")

def profile_function(frame, event, arg):
    if event == "call":
        start_times[frame.f_code] = time.perf_counter()
        call_stack.append((frame.f_code, frame.f_lineno))
    elif event == "return":
        end_time = time.perf_counter()
        start_time = start_times.get(frame.f_code)
        if start_time:
            execution_time = end_time - start_time
            if execution_time > LONG_FUNCTION_THRESHOLD:
                indentation = '  ' * (len(call_stack) - 1)
                function_name = frame.f_code.co_name
                function_line = frame.f_lineno
                function_file = frame.f_code.co_filename
                print(f"{indentation}Function '{function_name}' (Line {function_line}, File: {function_file}) "
                      f"took {execution_time:.4f} seconds")
            call_stack.pop()

def set_profiler():
    if log_long_functions:
        sys.setprofile(profile_function)
    else:
        sys.setprofile(log_function_calls)
        

def translate_texture_path(file_path):
    base_filename = os.path.basename(file_path)
    name_without_ext = os.path.splitext(base_filename)[0]
    target_filename = f"{name_without_ext}_result.png"
    return os.path.join("textures", target_filename)

def center_window(root, width, height):
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2) - 25
    root.geometry(f"{width}x{height}+{x}+{y}")

def get_key_by_name(dictionary, target_name):
        for key, value in dictionary.items():
            if value.get("name") == target_name:  # Check if the 'name' matches the target
                return key
        return None  # Return None if no match is found
    
    