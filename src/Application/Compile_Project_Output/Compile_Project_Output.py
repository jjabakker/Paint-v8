"""
This function takes as input the directory under which the various experiments are held.
It will create an Output directory with three files: All Squares, All Images, and Images Summary.
"""
import os
import time
from tkinter import *
from tkinter import ttk, filedialog

import pandas as pd

from src.Application.Generate_Squares.Utilities.Generate_Squares_Support_Functions import is_likely_root_directory
from src.Application.Utilities.General_Support_Functions import (
    get_default_locations,
    save_default_locations,
    read_experiment_file,
    read_squares_from_file,
    format_time_nicely,
    correct_all_images_column_types)
from src.Application.Utilities.Paint_Messagebox import paint_messagebox
from src.Common.Support.DirectoriesAndLocations import (
    get_experiment_squares_file_path,
    get_squares_file_path)
from src.Common.Support.LoggerConfig import (
    paint_logger,
    paint_logger_change_file_handler_name,
    paint_logger_file_name_assigned)

if not paint_logger_file_name_assigned:
    paint_logger_change_file_handler_name('Compile Output.log')


# -----------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------
# The routine that does the work
# -----------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------

def compile_project_output(project_dir: str, verbose: bool):

    paint_logger.info("")
    paint_logger.info(f"Compiling output for {project_dir}")
    time_stamp = time.time()

    # Create the dataframes to be filled
    df_all_images = pd.DataFrame()
    df_all_squares = pd.DataFrame()
    df_image_summary = pd.DataFrame()

    experiment_dirs = os.listdir(project_dir)
    experiment_dirs.sort()

    for experiment_names in experiment_dirs:

        experiment_dir_path = os.path.join(project_dir, experiment_names)
        if not os.path.isdir(experiment_dir_path) or 'Output' in experiment_names or experiment_names.startswith('-'):
            continue

        if verbose:
            paint_logger.debug(f'Adding directory: {experiment_dir_path}')

        # Read the experiment_squares file to determine which images there are
        experiment_squares_file_path = get_experiment_squares_file_path(experiment_dir_path)
        df_experiment_squares = read_experiment_file(experiment_squares_file_path, only_records_to_process=True)
        if df_experiment_squares is None:
            paint_logger.error(
                f"Function 'compile_squares_file' failed: File {experiment_squares_file_path} does not exist")
            exit()

        for index, row in df_experiment_squares.iterrows():

            recording_name = row['Ext Recording Name']
            if row['Exclude']:  # Skip over images that are Excluded
                continue

            squares_file_path = get_squares_file_path(experiment_dir_path, recording_name)
            df_squares = read_squares_from_file(squares_file_path)

            if df_squares is None:
                paint_logger.error(
                    f'Compile Squares: No squares file found for image {recording_name} in the directory {experiment_names}')
                continue
            if len(df_squares) == 0:  # Ignore it when it is empty
                continue

            df_all_squares = pd.concat([df_all_squares, df_squares])

        # Determine how many unique for cell type, probe type, adjuvant, and probe there are in the batch
        row = [
            experiment_names,
            df_experiment_squares['Cell Type'].nunique(),
            df_experiment_squares['Probe Type'].nunique(),
            df_experiment_squares['Adjuvant'].nunique(),
            df_experiment_squares['Probe'].nunique()]

        # Add the data to the all_dataframes
        df_image_summary = pd.concat([df_image_summary, pd.DataFrame([row])])
        df_all_images = pd.concat([df_all_images, df_experiment_squares])

    # -----------------------------------------------------------------------------
    # At this point we have the df_all_images, df_all_squares and df_image_summary complete.
    # It is a matter of fine tuning now
    # -----------------------------------------------------------------------------

    # ----------------------------------------
    # Add data from df_all_images to df_all_squares
    # ----------------------------------------

    list_of_images = df_all_squares['Ext Recording Name'].unique().tolist()
    for image in list_of_images:

        # Get data from df_experiment_squares to add to df_all_squares
        probe = df_all_images.loc[image]['Probe']
        probe_type = df_all_images.loc[image]['Probe Type']
        adjuvant = df_all_images.loc[image]['Adjuvant']
        cell_type = df_all_images.loc[image]['Cell Type']
        concentration = df_all_images.loc[image]['Concentration']
        threshold = df_all_images.loc[image]['Threshold']
        recording_size = df_all_images.loc[image]['Recording Size']
        condition_nr = df_all_images.loc[image]['Condition Nr']
        recording_sequence_nr = df_all_images.loc[image]['Recording Sequence Nr']
        neighbour_setting = df_all_images.loc[image]['Neighbour Mode']

        # It can happen that image size is not filled in, handle that event
        # I don't think this can happen anymore, but leave for now
        try:
            recording_size = int(recording_size)
        except (ValueError, TypeError):
            # If the specified images size was not valid (not a number), set it to 0
            df_all_squares.loc[df_all_squares['Ext Recording Name'] == image, 'Recording Size'] = 0
            paint_logger.error(f"Invalid image size in {image}")

        # Add the data that was obtained from df_all_images
        df_all_squares.loc[df_all_squares['Ext Recording Name'] == image, 'Probe'] = probe
        df_all_squares.loc[df_all_squares['Ext Recording Name'] == image, 'Probe Type'] = probe_type
        df_all_squares.loc[df_all_squares['Ext Recording Name'] == image, 'Adjuvant'] = adjuvant
        df_all_squares.loc[df_all_squares['Ext Recording Name'] == image, 'Cell Type'] = cell_type
        df_all_squares.loc[df_all_squares['Ext Recording Name'] == image, 'Concentration'] = concentration
        df_all_squares.loc[df_all_squares['Ext Recording Name'] == image, 'Threshold'] = threshold
        df_all_squares.loc[df_all_squares['Ext Recording Name'] == image, 'Condition Nr'] = int(condition_nr)
        df_all_squares.loc[df_all_squares['Ext Recording Name'] == image, 'Recording Sequence Nr'] = int(recording_sequence_nr)
        df_all_squares.loc[df_all_squares['Ext Recording Name'] == image, 'Neighbour Mode'] = neighbour_setting

    # Ensure column types are correct
    correct_all_images_column_types(df_all_images)

    # Drop irrelevant columns in df_all_squares
    # df_all_squares = df_all_squares.drop(['Neighbour Visible', 'Variability Visible', 'Density Ratio Visible'], axis=1)

    # Drop the squares that have no tracks
    df_all_squares = df_all_squares[df_all_squares['Nr Tracks'] != 0]

    # Change recording_name to recording_name
    df_all_squares.rename(columns={'Ext Recording Name': 'Recording Name'}, inplace=True)

    # Set the columns for df_image_summary
    df_image_summary.columns = ['Recording', 'Nr Cell Types', 'Nr Probe Types', 'Adjuvants', 'Nr Probes']

    # ------------------------------------
    # Save the files
    # -------------------------------------

    # Check if Output directory exists, create if necessary
    os.makedirs(os.path.join(project_dir, "Output"), exist_ok=True)

    # Save the files,
    df_all_squares.to_csv(os.path.join(project_dir, 'Output', 'All Squares.csv'), index=False)
    df_all_images.to_csv(os.path.join(project_dir, 'Output', 'All Images.csv'), index=False)
    df_image_summary.to_csv(os.path.join(project_dir, "Output", "Image Summary.csv"), index=False)

    # Save a copy for easy Imager Viewer access
    df_all_images.to_csv(os.path.join(project_dir, 'All Images.csv'), index=False)

    run_time = time.time() - time_stamp
    paint_logger.info(f"Compiled  output for {project_dir} in {format_time_nicely(run_time)}")
    paint_logger.info("")


class CompileDialog:

    def __init__(self, _root):
        self.root = _root

        self.root.title('Compile Square Data')

        self.root_directory, self.paint_directory, self.images_directory, self.level = get_default_locations()

        content = ttk.Frame(self.root)
        frame_buttons = ttk.Frame(content, borderwidth=5, relief='ridge')
        frame_directory = ttk.Frame(content, borderwidth=5, relief='ridge')

        #  Do the lay-out
        content.grid(column=0, row=0)
        frame_directory.grid(column=0, row=1, padx=5, pady=5)
        frame_buttons.grid(column=0, row=2, padx=5, pady=5)

        # Fill the button frame
        btn_compile = ttk.Button(frame_buttons, text='Compile', command=self.on_compile_pressed)
        btn_exit = ttk.Button(frame_buttons, text='Exit', command=self.on_exit_pressed)
        btn_compile.grid(column=0, row=1)
        btn_exit.grid(column=0, row=2)

        # Fill the directory frame
        btn_root_dir = ttk.Button(frame_directory, text='Project Directory', width=15, command=self.change_root_dir)
        self.lbl_root_dir = ttk.Label(frame_directory, text=self.root_directory, width=80)

        btn_root_dir.grid(column=0, row=0, padx=10, pady=5)
        self.lbl_root_dir.grid(column=1, row=0, padx=20, pady=5)

    def change_root_dir(self) -> None:
        self.root_directory = filedialog.askdirectory(initialdir=self.root_directory)
        save_default_locations(self.root_directory, self.paint_directory, self.images_directory, self.level)
        if len(self.root_directory) != 0:
            self.lbl_root_dir.config(text=self.root_directory)

    def on_compile_pressed(self) -> None:
        # Check if the directory is a likely project directory
        if is_likely_root_directory(self.root_directory):
            compile_project_output(project_dir=self.root_directory, verbose=True)
            self.root.destroy()
        else:
            paint_logger.error("The selected directory does not seem to be a project directory")
            paint_messagebox(self.root, title='Warning', message="The selected directory does not seem to be a project directory")

    def on_exit_pressed(self) -> None:
        self.root.destroy()


if __name__ == "__main__":
    root = Tk()
    root.eval('tk::PlaceWindow . center')
    CompileDialog(root)
    root.mainloop()
