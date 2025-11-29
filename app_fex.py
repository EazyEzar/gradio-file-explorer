import gradio as gr
import os
import zipfile
import shutil
import tempfile
from pathlib import Path
import pandas as pd
import math

# --- Configuration ---
# Set the root directory the explorer is allowed to access.
# os.path.expanduser("~") starts in the user's home directory.
# Use "/" for the entire filesystem (use with caution).
ROOT_DIR = "/" #os.path.abspath(os.path.expanduser("~"))

# --- State Management ---
# Using a class to manage state more cleanly than global variables.
class FileExplorerState:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.current_path = root_dir

    def set_path(self, new_path):
        """Safely sets the current path, ensuring it's within the root directory."""
        # Normalize and resolve the path
        abs_path = os.path.abspath(os.path.join(self.current_path, new_path))
        
        # Security check: Prevent escaping the root directory
        if os.path.commonpath([self.root_dir, abs_path]) != self.root_dir:
            print(f"Warning: Access denied. Attempted to access path outside of root: {abs_path}")
            return self.current_path # Return old path
            
        if os.path.isdir(abs_path):
            self.current_path = abs_path
        return self.current_path

    def go_up(self):
        """Navigates to the parent directory."""
        parent = os.path.dirname(self.current_path)
        # Prevent going above the root directory
        if len(parent) < len(self.root_dir):
            self.current_path = self.root_dir
        else:
            self.current_path = parent
        return self.current_path

# Instantiate the state manager
state = FileExplorerState(ROOT_DIR)

# --- Helper Functions ---
def format_size(size_bytes):
    """Formats size in bytes to a human-readable string."""
    if size_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

# --- Core Functions ---

def build_file_list(path):
    """
    Builds a list of dictionaries for the contents of a given path.
    """
    items_list = []
    try:
        # Sort items, directories first, then files, all case-insensitively
        items = os.listdir(path)
        items.sort(key=lambda x: (os.path.isfile(os.path.join(path, x)), x.lower()))
        for item in items:
            item_path = os.path.join(path, item)
            is_dir = os.path.isdir(item_path)
            size = format_size(os.path.getsize(item_path)) if not is_dir else "-"
            items_list.append({
                "name": item,
                "type": "📁" if is_dir else "📄",
                "size": size
            })
    except (IOError, OSError, PermissionError) as e:
        print(f"Error reading path {path}: {e}")
    return items_list

def create_zip_and_get_link(df, current_path, progress=gr.Progress()):
    """
    Creates a zip file from the selected checkboxes in the DataFrame.
    """
    # --- NEW LOGIC: Extract paths directly from the DataFrame ---
    selected_paths = []
    if df is not None and not df.empty:
        for index, row in df.iterrows():
            # Check column 'Select' (case insensitive string or boolean check)
            if str(row['Select']).lower() == 'true':
                selected_paths.append(os.path.join(current_path, row['Name']))
    # -----------------------------------------------------------

    if not selected_paths:
        gr.Warning("No files or folders selected for download.")
        return None

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "download.zip")
    
    progress(0, desc="Starting zip process...")
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            total_items = len(selected_paths)
            for i, path_str in enumerate(selected_paths):
                full_path = os.path.abspath(path_str)
                # Security check
                if os.path.commonpath([state.root_dir, full_path]) != state.root_dir:
                    print(f"Skipping unauthorized path: {full_path}")
                    continue
                
                progress((i) / total_items, desc=f"Zipping: {os.path.basename(full_path)}")

                if os.path.isdir(full_path):
                    for root, _, files in os.walk(full_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, current_path)
                            zipf.write(file_path, arcname)
                elif os.path.isfile(full_path):
                    arcname = os.path.relpath(full_path, current_path)
                    zipf.write(full_path, arcname)
        
        progress(1, desc="Zip creation complete!")
        gr.Info(f"Successfully zipped {len(selected_paths)} items.")
        return zip_path
    except Exception as e:
        gr.Error(f"Failed to create ZIP file: {e}")
        print(f"Error creating zip file: {e}")
        shutil.rmtree(temp_dir)
        return None
def upload_files(file_paths, current_path):
    """
    Moves uploaded files from Gradio's temp storage to the current directory.
    """
    if not file_paths:
        gr.Warning("No files selected to upload.")
        return update_file_display(current_path) + (None,) # Keep current state

    saved_count = 0
    try:
        for temp_file_path in file_paths:
            # Get the original filename
            filename = os.path.basename(temp_file_path)
            destination = os.path.join(current_path, filename)
            
            # Copy/Move the file
            shutil.move(temp_file_path, destination)
            saved_count += 1
            
        gr.Info(f"Successfully uploaded {saved_count} files.")
    except Exception as e:
        gr.Error(f"Error uploading files: {e}")
        print(f"Upload error: {e}")

    # Return the updated file list (unpack the tuple from update_file_display)
    # Plus 'None' to clear the file uploader component
    return update_file_display(current_path) + (None,)
    
# --- Gradio Interface ---
with gr.Blocks() as demo:
    
    # Hidden state to store the list of selected file paths as a string
    selected_paths_state = gr.Textbox(value="", visible=False)

    gr.Markdown("# 🌳 File Explorer")
    gr.Markdown("Browse the file system, select items, and download them as a ZIP file.")

    with gr.Row():
        path_input = gr.Textbox(
            label="Current Path",
            value=state.current_path,
            interactive=True
        )
        up_button = gr.Button("⬆️ Up", scale=0)
        refresh_button = gr.Button("🔄 Refresh", scale=0)

    with gr.Row():
        with gr.Column(scale=3): # Increased scale for the new column
            gr.Markdown("### Files and Folders (Click folder name to enter, checkbox to select)")
            file_list_df = gr.DataFrame(
                headers=["Select", "Type", "Name", "Size"],
                datatype=["bool", "str", "str", "str"],
                # FIX: Make only the 'Select' column interactive to prevent edit mode on others.
                interactive=[True, False, False, False],
                row_count=(1, "dynamic"),
                col_count=(4, "fixed")
            )

        with gr.Column(scale=1):
            gr.Markdown("### Actions")
            with gr.Group():
                with gr.Accordion("📂 Upload Files", open=True):
                    file_uploader = gr.File(
                        label="Drop files here",
                        file_count="multiple", 
                        type="filepath"
                    )
                    upload_btn = gr.Button("⬆️ Upload to Current Folder", variant="primary")
                # --- NEW UPLOAD SECTION END ---

                gr.Markdown("---") # Just a visual separator
                download_button = gr.Button("Download Selected as ZIP", variant="primary")
                download_link = gr.File(label="Download ZIP", interactive=False)
                
                with gr.Accordion("Delete Files", open=False):
                    confirm_delete_checkbox = gr.Checkbox(label="⚠️ Confirm permanent deletion", value=False)
                    delete_button = gr.Button("Delete Selected", variant="stop")

                gr.Markdown("**Selected Items:**")
                selected_display = gr.Markdown("None")

    # --- Event Handling & Logic ---

    def update_file_display(path):
        """Updates the DataFrame with the contents of the new path."""
        file_list = build_file_list(path)
        # Create a pandas DataFrame to populate the component
        df = pd.DataFrame([[False, item['type'], item['name'], item['size']] for item in file_list], columns=["Select", "Type", "Name", "Size"])
        # Reset selections on path change
        return path, df, "None", "", False # Reset confirm delete checkbox

    def handle_selection_change(df: pd.DataFrame, current_path: str):
        """
        Processes changes in the DataFrame (checkboxes) to update the selected list.
        """
        selected_items = []
        # Use a more robust check for the boolean value from the DataFrame,
        # as it might be passed as a string 'true'/'false'.
        for index, row in df.iterrows():
            # Check the value in the 'Select' column
            if str(row['Select']).lower() == 'true':
                item_name = row['Name']
                item_path = os.path.join(current_path, item_name)
                selected_items.append(item_path)
        
        selected_paths_str = ",".join(selected_items)
        # Use a Markdown list for better formatting
        if selected_items:
            # Create a multi-line string with a dash for each item
            display_str = "\n".join([f"- {os.path.basename(p)}" for p in selected_items])
        else:
            display_str = "None"
        
        return selected_paths_str, display_str

    def handle_row_select(evt: gr.SelectData, df_data: pd.DataFrame, current_path: str, current_display: str, current_selected: str, confirm_del: bool):
        """
        Handles clicking on a row to navigate into directories.
        """
        # evt.index[0] is the row index, evt.index[1] is the column index
        if evt.index[1] == 2: # Column 2 is the 'Name' column
            selected_row_series = df_data.iloc[evt.index[0]]
            
            item_type = selected_row_series['Type']
            item_name = selected_row_series['Name']
            
            if item_type == "📁": # It's a directory
                new_path = os.path.join(current_path, item_name)
                state.set_path(new_path)
                return update_file_display(state.current_path)

        # --- CRITICAL FIX ---
        # If we clicked a Checkbox or a File (not a folder), we must NOT return the old data.
        # Returning inputs here would overwrite the checkbox state that just changed.
        # gr.skip() tells Gradio: "Ignore this event, don't update any outputs."
        return gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()

    def delete_selected_items(df, confirm_delete, current_path):
        """Deletes the selected files and folders after confirmation."""
        if not confirm_delete:
            gr.Warning("Deletion not confirmed. Please check the confirmation box.")
            return update_file_display(current_path)

        # --- NEW LOGIC: Extract paths directly from the DataFrame ---
        selected_paths = []
        if df is not None and not df.empty:
            for index, row in df.iterrows():
                if str(row['Select']).lower() == 'true':
                    selected_paths.append(os.path.join(current_path, row['Name']))
        # -----------------------------------------------------------

        if not selected_paths:
            gr.Warning("No items selected to delete.")
            return update_file_display(current_path)

        deleted_count = 0
        error_count = 0
        for path_str in selected_paths:
            full_path = os.path.abspath(path_str)
            # Security check
            if os.path.commonpath([state.root_dir, full_path]) != state.root_dir:
                print(f"Skipping unauthorized delete path: {full_path}")
                error_count += 1
                continue
            
            try:
                if os.path.isfile(full_path):
                    os.remove(full_path)
                    deleted_count += 1
                elif os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                    deleted_count += 1
            except Exception as e:
                print(f"Error deleting {full_path}: {e}")
                error_count += 1
        
        gr.Info(f"Deleted {deleted_count} items. Failed to delete {error_count} items.")
        
        # Refresh the file list
        return update_file_display(current_path)

    # --- Component Triggers ---
    
    def handle_path_update(new_path):
        state.set_path(new_path)
        return update_file_display(state.current_path)

    def handle_go_up():
        state.go_up()
        return update_file_display(state.current_path)

    def handle_refresh(current_path):
        return update_file_display(current_path)

    demo.load(
        fn=update_file_display,
        inputs=[path_input],
        outputs=[path_input, file_list_df, selected_display, selected_paths_state, confirm_delete_checkbox]
    )

    path_input.submit(handle_path_update, inputs=[path_input], outputs=[path_input, file_list_df, selected_display, selected_paths_state, confirm_delete_checkbox])
    up_button.click(handle_go_up, inputs=[], outputs=[path_input, file_list_df, selected_display, selected_paths_state, confirm_delete_checkbox])
    refresh_button.click(handle_refresh, inputs=[path_input], outputs=[path_input, file_list_df, selected_display, selected_paths_state, confirm_delete_checkbox])

    file_list_df.change(
        fn=handle_selection_change,
        inputs=[file_list_df, path_input],
        outputs=[selected_paths_state, selected_display]
    )
    
    file_list_df.select(
        fn=handle_row_select,
        # ADDED confirm_delete_checkbox to inputs
        inputs=[file_list_df, path_input, selected_display, selected_paths_state, confirm_delete_checkbox],
        # ADDED confirm_delete_checkbox to outputs
        outputs=[path_input, file_list_df, selected_display, selected_paths_state, confirm_delete_checkbox]
    )

    download_button.click(
        fn=create_zip_and_get_link,
        inputs=[file_list_df, path_input], 
        outputs=[download_link]
    )
    
    delete_button.click(
        fn=delete_selected_items,
        inputs=[file_list_df, confirm_delete_checkbox, path_input],
        outputs=[path_input, file_list_df, selected_display, selected_paths_state, confirm_delete_checkbox]
    )
    
    upload_btn.click(
        fn=upload_files,
        inputs=[file_uploader, path_input],
        outputs=[
            path_input, 
            file_list_df, 
            selected_display, 
            selected_paths_state, 
            confirm_delete_checkbox, 
            file_uploader # This is the extra output to clear the box
        ]
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7861, debug=True, share=True)
