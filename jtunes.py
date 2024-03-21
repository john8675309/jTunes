#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango, GdkPixbuf
import os
import sqlite3
from appdirs import user_config_dir
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
import threading
import base64
from io import BytesIO
import pygame
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from threading import Timer

def get_icon_base64():
    # Return the Base64 encoded string of your icon
    file_path = "icon_base64.txt"
    # Read the Base64 encoded string from the file
    #return """
    #YOUR_BASE64_ENCODED_STRING_HERE
    #"""
    with open(file_path, "r") as file:
        icon_base64 = file.read()
    return icon_base64

class MainWindow(Gtk.Window):
    def __init__(self):
        pygame.mixer.init()
        Gtk.Window.__init__(self, title="jTunes")
        self.connect("destroy", self.on_destroy)
        self.set_default_size(800, 600)
        self.keep_running = False
        self.is_playing = False
        self.current_song_pos_ms = 0
        self.treeview = Gtk.TreeView()
        self.current_filter_text = ""
        window_width = 800  # Your window's initial width
        num_columns = 5  # The number of columns
        padding = 20  # Adjust as needed
        initial_column_width = (window_width - (padding * num_columns)) / num_columns
        self.liststore = Gtk.ListStore(int, str, str, str, str, str)
        icon_base64 = get_icon_base64()
        icon_bytes = base64.b64decode(icon_base64)
        # Load the bytes into a GdkPixbuf.Pixbuf
        loader = GdkPixbuf.PixbufLoader()
        loader.write(icon_bytes)
        loader.close()
        icon_pixbuf = loader.get_pixbuf()
        self.icon_pixbuf = icon_pixbuf
        self.set_icon(icon_pixbuf)
        # Create a vertical box to hold the menu bar, top controls, and the main area
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Create the menu bar
        menu_bar = Gtk.MenuBar()

        # Create the "File" menu
        file_menu = Gtk.Menu()
        file_menu_item = Gtk.MenuItem(label="File")
        file_menu_item.set_submenu(file_menu)

        # Create the "Preferences" menu item
        preferences_menu_item = Gtk.MenuItem(label="Preferences")
        preferences_menu_item.connect("activate", self.on_preferences_clicked)
        file_menu.append(preferences_menu_item)

        # Create a separator
        separator_menu_item = Gtk.SeparatorMenuItem()
        file_menu.append(separator_menu_item)

        # Create the "Exit" menu item
        exit_menu_item = Gtk.MenuItem(label="Exit")
        exit_menu_item.connect("activate", self.on_exit_clicked)
        file_menu.append(exit_menu_item)

        menu_bar.append(file_menu_item)

        # Create the "About" menu
        about_menu = Gtk.Menu()
        about_menu_item = Gtk.MenuItem(label="About")
        about_menu_item.set_submenu(about_menu)

        # Create the "About jTunes" menu item
        about_jtunes_menu_item = Gtk.MenuItem(label="About jTunes")
        about_jtunes_menu_item.connect("activate", self.on_about_clicked)
        about_menu.append(about_jtunes_menu_item)

        menu_bar.append(about_menu_item)

        vbox.pack_start(menu_bar, False, False, 0)

        # Create the top controls
        top_controls = Gtk.Box(spacing=6)

        # Create a vertical box to hold the playback buttons and volume slider
        playback_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        playback_box.set_valign(Gtk.Align.CENTER)  # Center the playback box vertically

        # Create a horizontal box to hold the playback buttons
        button_box = Gtk.Box(spacing=6)

        # Add rewind button
        rewind_button = Gtk.Button.new_from_icon_name("media-seek-backward", Gtk.IconSize.BUTTON)
        button_box.pack_start(rewind_button, False, False, 0)

        # Add play/pause button
        play_button = Gtk.Button.new_from_icon_name("media-playback-start", Gtk.IconSize.BUTTON)
        self.play_button = play_button
        self.play_button.connect("clicked", self.on_play_pause_clicked)
        button_box.pack_start(play_button, False, False, 0)

        # Add fast forward button
        forward_button = Gtk.Button.new_from_icon_name("media-seek-forward", Gtk.IconSize.BUTTON)
        button_box.pack_start(forward_button, False, False, 0)

        playback_box.pack_start(button_box, False, False, 0)

        # Add volume slider below the playback buttons
        volume_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
        volume_slider.set_draw_value(False)
        volume_slider.set_size_request(-1, 20)  # Set height of the volume slider
        self.volume_slider = volume_slider
        playback_box.pack_start(volume_slider, False, False, 0)
        self.volume_slider.connect("value-changed", self.on_volume_changed)

        top_controls.pack_start(playback_box, False, False, 0)

        # Create a box to hold the "Now Playing" section
        now_playing_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        now_playing_box.set_border_width(10)
        self.now_playing_box = now_playing_box

        # Create a frame with a curved border
        now_playing_frame = Gtk.Frame()
        now_playing_frame.set_border_width(10)
        now_playing_frame.set_label_align(0.5, 0.5)  # Center the label
        now_playing_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)  # Set curved border
        self.now_playing_frame = now_playing_frame
        # Add "Now Playing" label to the frame
        self.now_playing_label = Gtk.Label(label="Now Playing")
        now_playing_frame.set_label_widget(self.now_playing_label)

        # Create a vertical box to hold the song title and playback slider
        now_playing_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        now_playing_content.set_border_width(10)
        self.now_playing_content = now_playing_content
        

        # Add song title label
        song_title_label = Gtk.Label(label="")
        song_title_label.set_justify(Gtk.Justification.CENTER)
        self.song_title_label =  song_title_label
        self.song_title_label.set_max_width_chars(30)
        self.song_title_label.set_ellipsize(Pango.EllipsizeMode.END)
        
        self.connect("size-allocate", self.on_window_size_changed)
        now_playing_content.pack_start(song_title_label, False, False, 0)

        # Add playback position slider
        playback_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        playback_slider.set_value(0)  # Set initial playback position
        playback_slider.set_draw_value(False)
        self.playback_slider = playback_slider
        self.is_slider_adjusting = False
        self.playback_slider.connect("button-release-event", self.on_slider_drag_finish)
        now_playing_content.pack_start(playback_slider, False, False, 0)

        now_playing_frame.add(now_playing_content)
        now_playing_box.pack_start(now_playing_frame, False, False, 0)

        top_controls.pack_start(now_playing_box, True, True, 0)

        # Create a vertical box to hold the search entry and a blank space
        search_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        search_box.set_valign(Gtk.Align.CENTER)  # Center the search box vertically

        # Create a horizontal box to hold the search entry and the magnifying glass icon
        search_entry_box = Gtk.Box(spacing=6)

        # Add search entry
        search_entry = Gtk.Entry()
        search_entry.set_width_chars(20)  # Set the width of the search entry
        search_entry_box.pack_start(search_entry, False, False, 0)
        self.search_entry = search_entry  # Assuming you've created this already
        self.search_entry.connect("changed", self.on_search_entry_changed)


        # Add magnifying glass icon
        magnifying_glass_icon = Gtk.Image.new_from_icon_name("edit-find", Gtk.IconSize.BUTTON)
        search_entry_box.pack_start(magnifying_glass_icon, False, False, 0)

        search_box.pack_start(search_entry_box, False, False, 0)

        # Add a blank label to create space below the search entry
        blank_label = Gtk.Label(label="")
        blank_label.set_size_request(-1, 20)  # Set the height of the blank label
        search_box.pack_start(blank_label, False, False, 0)

        top_controls.pack_end(search_box, False, False, 0)

        vbox.pack_start(top_controls, False, False, 0)

        # Create a horizontal paned to hold the side column and the TreeView
        hpaned = Gtk.HPaned()

        # Create the side column (TreeView)
        side_treeview = Gtk.TreeView()
        renderer_text = Gtk.CellRendererText()
        column_text = Gtk.TreeViewColumn("Source", renderer_text, text=0)
        side_treeview.append_column(column_text)

        # Create a ListStore for the side column data
        side_liststore = Gtk.ListStore(str)
        side_liststore.append(["Library"])
        #side_liststore.append(["Radio"])
        #side_liststore.append(["Twentieth Century Blues"])
        # Add more items as needed
        side_treeview.set_model(side_liststore)
        self.side_treeview = side_treeview
        selection = self.side_treeview.get_selection()
        selection.connect("changed", self.on_side_selection_changed)
        self.select_default_side_item()
        # Create a scrollable container for the side column
        side_scrolled_window = Gtk.ScrolledWindow()
        side_scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        side_scrolled_window.add(side_treeview)

        # Increase the default width of the side column
        side_scrolled_window.set_min_content_width(200)

        # Create the main TreeView
        self.treeview = Gtk.TreeView()
        self.treeview.connect("row-activated", self.on_row_activated)

        # Create columns for the main TreeView
        renderer_text = Gtk.CellRendererText()
        column_song_name = Gtk.TreeViewColumn("Song Name", renderer_text, text=1)
        column_time = Gtk.TreeViewColumn("Time", renderer_text, text=2)
        column_artist = Gtk.TreeViewColumn("Artist", renderer_text, text=3)
        column_album = Gtk.TreeViewColumn("Album", renderer_text, text=4)
        column_genre = Gtk.TreeViewColumn("Genre", renderer_text, text=5)

        column_song_name.set_fixed_width(initial_column_width)
        column_time.set_fixed_width(initial_column_width)
        column_artist.set_fixed_width(initial_column_width)
        column_album.set_fixed_width(initial_column_width)
        column_genre.set_fixed_width(initial_column_width)


        column_song_name.set_sort_column_id(1)
        column_time.set_sort_column_id(2)
        column_artist.set_sort_column_id(3) 
        column_album.set_sort_column_id(4)
        column_genre.set_sort_column_id(5) 

        column_genre.set_resizable(True)
        column_album.set_resizable(True)
        column_artist.set_resizable(True)
        column_time.set_resizable(True)
        column_song_name.set_resizable(True)

        self.treeview.append_column(column_song_name)
        self.treeview.append_column(column_time)
        self.treeview.append_column(column_artist)
        self.treeview.append_column(column_album)
        self.treeview.append_column(column_genre)

        # Create a scrollable container for the main TreeView
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.add(self.treeview)

        # Add the side column and main TreeView to the horizontal paned
        hpaned.add1(side_scrolled_window)
        hpaned.add2(scrolled_window)

        # Set the initial position of the paned separator
        hpaned.set_position(200)

        vbox.pack_start(hpaned, True, True, 0)

        # Add the vertical box to the main window
        self.add(vbox)
        self.init_database()
        self.add_column_if_not_exists('preferences', 'volume', 'REAL DEFAULT 0.5')
        self.add_column_if_not_exists('preferences', 'min_to_tray', 'INTEGER DEFAULT 0')
        self.add_column_if_not_exists('mp3_files', 'play_count', 'INTEGER DEFAULT 0')
        self.connect("delete-event", self.on_main_window_delete_event)
        pygame.mixer.music.set_volume(self.load_volume_setting())
        volume_slider.set_value(self.load_volume_setting())
        # Attempt to load the previously selected music directory
        music_directory = self.load_music_directory()
        
        if music_directory:
            # If a music directory is found, start scanning it in a new thread
            threading.Thread(target=self.scan_music_directory, args=(music_directory,)).start()
        # Populate the main TreeView with sample data
        self.create_tray_icon()
    def on_search_entry_changed(self, entry):
        """Called whenever the text in the search entry changes."""
        self.current_filter_text = entry.get_text()  # Update the current filter text
        self.filter.refilter()  # Refilter the treeview

    def select_default_side_item(self):
        # Select the first row in the side list (Library)
        selection = self.side_treeview.get_selection()
        selection.select_path(Gtk.TreePath(0))
    def display_library_content(self):
        if self.treeview is not None:
            self.populate_treeview()
        
    def on_side_selection_changed(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter:
            selected_item = model[treeiter][0]  # Get the name of the selected item

            # Respond to the selection
            if selected_item == "Library":
                self.init_database()
                self.display_library_content()
            elif selected_item == "Radio":
                # Logic to display Radio content
                pass
            elif selected_item == "Twentieth Century Blues":
                # Logic for Twentieth Century Blues
                pass
    def update_play_pause_button(self):
        # Update the button icon and tooltip based on play/pause state
        if self.is_playing:
            self.play_button.set_image(Gtk.Image.new_from_icon_name("media-playback-pause", Gtk.IconSize.BUTTON))
            self.play_button.set_tooltip_text("Pause")
        else:
            self.play_button.set_image(Gtk.Image.new_from_icon_name("media-playback-start", Gtk.IconSize.BUTTON))
            self.play_button.set_tooltip_text("Play")
    def on_play_pause_clicked(self,widget):
        selection = self.treeview.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter is None:
            model = self.treeview.get_model()
            first_iter = model.get_iter_first()
            selection.select_iter(first_iter)
            # Update model and treeiter to reflect the new selection
            model, treeiter = selection.get_selected()
            if treeiter:
                song_id = model[treeiter][0]  # Assuming the ID is in the first column
                self.play_song(song_id)
        if self.is_playing:
            pygame.mixer.music.pause()
            self.is_playing = False
            self.update_play_pause_button()
        else:
            pygame.mixer.music.unpause()
            self.is_playing = True
            self.update_play_pause_button()

            
    def save_volume_setting(self, volume):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Assuming you're updating a single row in the preferences table
        cursor.execute("UPDATE preferences SET volume = ?", (volume,))
        conn.commit()
        conn.close()

    def load_volume_setting(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT volume FROM preferences LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
           return row[0]  # Return the volume level
        return 0.8  # Default volume if not set
    
    def column_exists(self,table_name, column_name):
        """Check if a column exists in a table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        self.columns = [info[1] for info in cursor.fetchall()]
        return column_name in self.columns

    def add_column_if_not_exists(self,table_name, column_name, column_type):
        """Add a column to a table if it does not already exist."""
        conn = sqlite3.connect(self.db_path)
        if not self.column_exists(table_name, column_name):
            cursor = conn.cursor()
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            conn.commit()
     # Column names are in the second position
        return column_name in self.columns
    def on_volume_changed(self,slider):
        new_pos = self.volume_slider.get_value()
        pygame.mixer.music.set_volume(new_pos)
        self.save_volume_setting(new_pos)

    def init_database(self):
        # Get the user's configuration directory
        config_dir = user_config_dir("jTunes", "JohnHass")
        os.makedirs(config_dir, exist_ok=True)

        # Create the database file path
        self.db_path = os.path.join(config_dir, "jtunes.db")

        # Create the database table if it doesn't exist
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY,
                music_directory TEXT
            )
        """)
        conn.commit()
        conn.close()

    def on_preferences_clicked(self, widget):
        # Create the preferences dialog
        dialog = Gtk.Dialog(title="Preferences", transient_for=self, modal=True)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", Gtk.ResponseType.OK)

        # Create a box to hold the preferences content
        content_box = dialog.get_content_area()
        content_box.set_spacing(10)
        content_box.set_border_width(10)

        # Create a label for the music directory selection
        label = Gtk.Label(label="Music Directory:")
        content_box.pack_start(label, False, False, 0)

        # Create a file chooser button for selecting the music directory
        file_chooser = Gtk.FileChooserButton(title="Select Music Directory")
        file_chooser.set_action(Gtk.FileChooserAction.SELECT_FOLDER)
        content_box.pack_start(file_chooser, False, False, 0)

        # Load the current music directory from the database
        music_directory = self.load_music_directory()
        if music_directory:
            file_chooser.set_current_folder(music_directory)
        min_to_tray_checkbox = Gtk.CheckButton(label="Minimize to Tray")
        min_to_tray_value = self.load_min_to_tray_setting()  # Assuming you implement this method
        min_to_tray_checkbox.set_active(min_to_tray_value == 1)

        min_to_tray_checkbox.connect("toggled", self.on_min_to_tray_toggled)
        content_box.pack_start(min_to_tray_checkbox, False, False, 0)


        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            # Save the selected music directory to the database
            selected_directory = file_chooser.get_filename()
            self.save_music_directory(selected_directory)
            selected_directory = file_chooser.get_filename()
            self.save_music_directory(selected_directory)
            threading.Thread(target=self.scan_music_directory, args=(selected_directory,)).start()

        dialog.destroy()
    def on_main_window_delete_event(self, widget, event):
        min_to_tray = self.load_min_to_tray_setting()
        if min_to_tray == 1:
            self.hide()
            #self.hide_on_delete()  # This prevents the window from being destroyed
            return True  # This stops the event from propagating further
        return False
    def on_tray_icon_activate(self, icon):
        if self.is_visible():
            self.hide()
        else:
            self.show_all()
    def create_tray_icon(self):
        self.tray_icon = Gtk.StatusIcon()
        self.tray_icon.set_from_pixbuf(self.icon_pixbuf)
        self.tray_icon.connect("activate", self.on_tray_icon_activate)
        self.tray_icon.set_tooltip_text("jTunes")
        self.tray_icon.set_visible(True)  
    def on_min_to_tray_toggled(self, checkbox):
        new_value = 1 if checkbox.get_active() else 0
        self.save_min_to_tray_setting(new_value)

    def save_min_to_tray_setting(self, value):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE preferences SET min_to_tray = ?", (value,))
        conn.commit()
        conn.close()
    def load_min_to_tray_setting(self): 
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT min_to_tray FROM preferences LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0
    def save_music_directory(self, directory):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO preferences (id, music_directory) VALUES (1, ?)", (directory,))
        conn.commit()
        conn.close()

    def load_music_directory(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT music_directory FROM preferences WHERE id = 1")
        result = cursor.fetchone()
        conn.close()

        if result:
            return result[0]
        else:
            return None

    def on_exit_clicked(self, widget):
        Gtk.main_quit()

    def on_about_clicked(self, widget):
        # Create an about dialog
        about_dialog = Gtk.AboutDialog(transient_for=self, modal=True)
        about_dialog.set_program_name("jTunes")
        about_dialog.set_version("0.0.1")
        about_dialog.set_copyright("© 2024 John Hass john8675309@gmail.com")
        about_dialog.set_comments("A simple music player")
        about_dialog.set_website("https://www.example.com")
        about_dialog.set_logo_icon_name("audio-x-generic")
        about_dialog.run()
        about_dialog.destroy()

    def populate_treeview(self):
        #liststore = Gtk.ListStore(int,str, str, str, str, str)
        # Assuming self.treeview is your Gtk.TreeView and it's associated with a ListStore or similar
        
        self.liststore.clear()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, song_name, length, artist, album, genre FROM mp3_files")
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            # Convert the length from seconds to mm:ss format
            try:
                length_seconds = float(row[2]) if row[2] else 0
            except ValueError:
                length_seconds = 0
            minutes = int(length_seconds // 60)
            seconds = int(length_seconds % 60)
            length_formatted = f"{minutes}:{seconds:02d}"  # Format seconds as two digits
            # Create a new tuple with the formatted length
            new_row = (row[0], row[1], length_formatted, row[3], row[4], row[5])
            self.liststore.append(new_row)
        #self.liststore = liststore
        self.filter = self.liststore.filter_new()  # Create a filter for the liststore
        self.filter.set_visible_func(self.filter_func)  # Set the filter function
        self.treeview.set_model(self.filter)
        #self.treeview.set_model(liststore)


    def filter_func(self, model, iter, data):
        """Determines if the row should be visible based on the search query."""
        if self.current_filter_text == "":
            return True
        for col_index in [1, 3, 4, 5]:
            value = model[iter][col_index]  # Get the value from the model at the given column index
            if value is None:
                # If the value is None, skip to the next column
                continue
            elif self.current_filter_text.lower() in value.lower():
                # If the current filter text is found in this column, return True
                return True

        # If the loop completes without finding a match, return False
        return False

    def scan_music_directory(self, directory):
        conn = sqlite3.connect(self.db_path)
        conn_reader = sqlite3.connect(self.db_path, timeout=10.0) 
        cursor_reader = conn_reader.cursor()
        cursor = conn.cursor()
        cursor.execute("""
         CREATE TABLE IF NOT EXISTS mp3_files (
                id INTEGER PRIMARY KEY,
                filename TEXT,
                song_name TEXT,
                length TEXT,
                artist TEXT,
                album TEXT,
                genre TEXT
            )
        """)
        conn.commit()

        self.update_now_playing_label("Scanning Music...")

        # Create a progress bar
        progress_bar = Gtk.ProgressBar()
        for child in self.now_playing_content.get_children():
            if isinstance(child, Gtk.Scale):
                self.now_playing_content.remove(child)
                break
        # Add the progress bar to the now_playing_box
        self.now_playing_content.pack_start(progress_bar, True, True, 0)
        progress_bar.show()

        # Get the total number of files to scan
        #total_files = sum(len(files) for _, _, files in os.walk(directory))
        total_files = sum(1 for _, _, files in os.walk(directory) for file in files if file.lower().endswith('.mp3'))
        files_scanned = 0

        def remove_deleted_files_from_db(self):
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
    
            # Retrieve all file paths from the database
            cursor.execute("SELECT id, filename FROM mp3_files")
            rows = cursor.fetchall()

            # Iterate through each file path
            for row in rows:
                file_id, filepath = row
                # Check if the file exists
                if not os.path.exists(filepath):
                    # If the file doesn't exist, delete its entry from the database
                    cursor.execute("DELETE FROM mp3_files WHERE id = ?", (file_id,))
    
            # Commit changes and close the connection
            conn.commit()
            conn.close()

        def file_exists_in_db(filepath):
            cursor_reader.execute("SELECT COUNT(*) FROM mp3_files WHERE filename = ?", (filepath,))
            return cursor_reader.fetchone()[0] > 0

        def update_progress_and_database(filepath, song_name, length, artist, album, genre):
            nonlocal files_scanned
            

            files_scanned += 1
            progress = files_scanned / total_files
            progress_bar.set_fraction(progress)
            artist_album_text = f"{artist} - {album} - {song_name}" if artist and album else ""
            self.song_title_label.set_text(artist_album_text)
            while Gtk.events_pending():
                Gtk.main_iteration()
            
            if files_scanned == total_files:
                self.song_title_label.set_text("")
                self.now_playing_content.remove(progress_bar)
                self.add_playback_slider()
                conn_reader.close()
            return False  # Return False to remove the idle callback

        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".mp3"):
                    filepath = os.path.join(root, file)
                    if not file_exists_in_db(filepath):
                        audio = EasyID3(filepath)
                        audio_l = MP3(filepath)
                        song_name = audio.get("title", [None])[0]
                        
                        length = audio_l.info.length
                        artist = audio.get("artist", [None])[0]
                        album = audio.get("album", [None])[0]
                        genre = audio.get("genre", [None])[0]
                        cursor.execute("INSERT INTO mp3_files (filename, song_name, length, artist, album, genre) VALUES (?, ?, ?, ?, ?, ?)", (filepath, song_name, length, artist, album, genre))
                        GLib.idle_add(update_progress_and_database, filepath, song_name, length, artist, album, genre)

                    else:
                        files_scanned += 1
                        progress = files_scanned / total_files
                        progress_bar.set_fraction(progress)
                        #self.song_title_label.set_text(filepath)
                        if files_scanned == total_files:
                            self.song_title_label.set_text("")
                            self.now_playing_content.remove(progress_bar)
                            self.add_playback_slider()
                            conn_reader.close()
                        while Gtk.events_pending():
                            Gtk.main_iteration()  
        conn.commit()
        conn.close()
        #conn_reader.close()        
        remove_deleted_files_from_db(self)
        self.update_now_playing_label("Now Playing")
        self.populate_treeview()

    def add_playback_slider(self):
        def add_slider():
            playback_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
            playback_slider.set_value(0)  # Set initial playback position
            playback_slider.set_draw_value(False)
            self.now_playing_content.pack_start(playback_slider, True, True, 0)
            self.playback_slider = playback_slider
            self.playback_slider.connect("button-release-event", self.on_slider_drag_finish)
            self.playback_slider.connect("button-press-event", self.on_slider_drag_start)
            playback_slider.show()  # Ensure the new widget is shown

        GLib.idle_add(add_slider)

    def update_now_playing_label(self, text):
        self.now_playing_label.set_text(text)

    def on_window_size_changed(self, widget, allocation):
        # Get the width of the now_playing_frame
        frame_width = self.now_playing_frame.get_allocated_width()

        # Calculate the maximum width for the song title label
        max_chars = (frame_width) // 10  # Adjust the divisor as needed

        # Update the maximum width of the song title label
        self.song_title_label.set_max_width_chars(max_chars)
    def stop_monitoring_playback(self):
        self.keep_running = False
    def on_slider_drag_start(self, slider, event):
        self.is_slider_adjusting = True
        #self.stop_monitoring_playback()

    def on_slider_drag_finish(self, slider, event):
        new_pos_ms = slider.get_value()
        self.current_song_pos_ms = new_pos_ms
        new_pos_sec = new_pos_ms / 1000
        if self.is_playing:
            # Only play if the playback was previously started
            new_pos_sec = new_pos_ms / 1000
            pygame.mixer.music.play(start=new_pos_sec)
        else:
            new_pos_sec = new_pos_ms / 1000
            pygame.mixer.music.play(start=new_pos_sec)
            self.is_playing = True
        self.update_play_pause_button()
        self.is_slider_adjusting = False
        
    def play_next_song(self):
        # Logic to determine the next song to play
        selection = self.treeview.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter:
            next_iter = model.iter_next(treeiter)
            if next_iter is None:
               # If we're at the end, start from the first song
               next_iter = model.get_iter_first()
            selection.select_iter(next_iter)
            song_id = model.get_value(next_iter, 0)  # Assuming the ID is in the first column
            self.play_song(song_id)
        self.is_playing = True
        self.update_play_pause_button()

    def monitor_playback(self):
        self.last_check = pygame.mixer.music.get_pos()
        while self.keep_running:
            if not self.is_slider_adjusting and self.is_playing:
                now = pygame.mixer.music.get_pos()
                if now == -1:
                    GLib.idle_add(self.play_next_song)
                    break
                if self.last_check != -1:
                    elapsed = now - self.last_check
                    self.current_song_pos_ms += elapsed
                    GLib.idle_add(self.playback_slider.set_value, self.current_song_pos_ms)

                self.last_check = now
            while Gtk.events_pending():
                Gtk.main_iteration()
            time.sleep(1)
    def play_song_now(self, filepath):
        audio = EasyID3(filepath)
        song_name = audio.get("title", [None])[0]
        artist = audio.get("artist", [None])[0]
        album = audio.get("album", [None])[0]
        artist_album_text = f"{artist} - {album} - {song_name}" if artist and album else ""
        self.song_title_label.set_text(artist_album_text)
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        self.is_playing = True
        self.update_play_pause_button()
        
        self.keep_running = True
        self.playBackthread = threading.Thread(target=self.monitor_playback, args=())
        self.playBackthread.start()
    def play_song(self, song_id):
        self.playback_slider.set_value(0)
        self.current_song_pos_ms = 0
        self.keep_running = False
        self.last_check=0
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT filename FROM mp3_files WHERE id = ?", (song_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            filepath = row[0]
            audio = MP3(filepath)
            length_seconds = audio.info.length
            length_milliseconds = length_seconds*1000
            adjustment = self.playback_slider.get_adjustment()
            adjustment.set_upper(length_milliseconds)
            self.playback_slider.set_value(0)
            threading.Thread(target=self.play_song_now, args=(filepath,)).start()
    def on_row_activated(self, tree_view, path, column):
        model = tree_view.get_model()
        iter = model.get_iter(path)
        songid = model.get_value(iter, 0)
        self.play_song(songid)
    def on_destroy(self, widget):
        self.should_run = False
        pygame.mixer.music.stop()
        self.keep_running = False
        Gtk.main_quit()
window = MainWindow()
#window.connect("destroy", self.on_destroy)
window.show_all()
Gtk.main()