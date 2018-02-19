# -*- coding: utf-8 -*-
"""
Created on Tue Jan  9 08:12:25 2018

@author: Andrew
"""

import sqlite3

import numpy as np
#Even though the library is referenced as cv2,
import cv2 as cv

import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from PIL import Image
from PIL import ImageTk

from functools import partial

import os
import datetime
import pickle
import hashlib

from threading import BoundedSemaphore
# http://tkinter.unpythonic.net/wiki/VerticalScrolledFrame

class VerticalScrolledFrame(tk.Frame):
    """A pure Tkinter scrollable frame that actually works!
    * Use the 'interior' attribute to place widgets inside the scrollable frame
    * Construct and pack/place/grid normally
    * This frame only allows vertical scrolling

    """
    def __init__(self, parent, *args, **kw):
        tk.Frame.__init__(self, parent, *args, **kw)            

        # create a canvas object and a vertical scrollbar for scrolling it
        vscrollbar = tk.Scrollbar(self, orient=tk.VERTICAL)
        vscrollbar.pack(fill=tk.Y, side=tk.RIGHT, expand=tk.FALSE)
        canvas = tk.Canvas(self, bd=0, highlightthickness=0,
                        yscrollcommand=vscrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.TRUE)
        vscrollbar.config(command=canvas.yview)

        # reset the view
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

        # create a frame inside the canvas which will be scrolled with it
        self.interior = interior = tk.Frame(canvas)
        interior_id = canvas.create_window(0, 0, window=interior,
                                           anchor=tk.NW)

        # track changes to the canvas and frame width and sync them,
        # also updating the scrollbar
        def _configure_interior(event):
            # update the scrollbars to match the size of the inner frame
            size = (interior.winfo_reqwidth(), interior.winfo_reqheight())
            canvas.config(scrollregion="0 0 %s %s" % size)
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the canvas's width to fit the inner frame
                canvas.config(width=interior.winfo_reqwidth())
        interior.bind('<Configure>', _configure_interior)

        def _configure_canvas(event):
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the inner frame's width to fill the canvas
                canvas.itemconfigure(interior_id, width=canvas.winfo_width())
        canvas.bind('<Configure>', _configure_canvas)



class Application:
    
    class ImageData:
        def __init__(self, ID, image, timestamp, contains_human):
            '''
            Default constructor, should not be used outside the ImageData class.
            '''
            self.ID = ID
            self.image = image
            self.timestamp = timestamp
            self.contains_human = contains_human
            
        @classmethod
        def from_file(cls, path, contains_human=0):
            '''
            Given a specified file path, instantiates an ImageData object.
            
            By default, the image does not contain a human.  All other fields
            are derived from the image file itself.
            
            This function is intended to create an ImageData object for an image
            file.
            '''
            #read image using OpenCV
            image     = cv.imread(path)
            timestamp = cls.__get_timestamp(path)
            ID        = cls.__compute_hash(image)
            
            return cls(ID, image, timestamp, contains_human)
        
        @classmethod
        def from_database(cls, ID, serialized_image, timestamp, contains_human):
            '''
            Given the four fields for an ImageData object, instantiates
            and returns an object.
            
            This function is intended to create an ImageData object for an image
            retrieved from the Image Database
            '''
            return cls(ID, cls.__deserialize(serialized_image), timestamp, contains_human)
        
        def serialize(self):
            return pickle.dumps(self.image)
        @staticmethod
        def __deserialize(data):
            return pickle.loads(data)
        @staticmethod
        def __get_timestamp(path):
            time = os.path.getmtime(path)
            return datetime.datetime.fromtimestamp(time)
        def __compute_hash(image):
            img_hasher      = hashlib.sha1()
            img_hasher.update(image)
            return img_hasher.hexdigest()
        def update(self, contains_human):
            self.contains_human = contains_human
           
    class Database:
        def __init__(self):
            self.connection = None
            self.cursor = None
        def is_open(self):
            return self.connection is not None
        def get_file_timestamp(self, file_path):
            time = os.path.getmtime(file_path)
            return datetime.datetime.fromtimestamp(time)
        
        def open_database(self, name):
            self.connection = sqlite3.connect(name)
            self.cursor = self.connection.cursor()
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS images(
                    id TEXT PRIMARY KEY,
                    img BLOB NOT NULL,
                    time_stamp TIMESTAMP NOT NULL,
                    contains_human BOOLEAN NOT NULL)''')
        def close_database(self):
            if self.connection is None:
                return
            self.connection.close()
            self.connection = None
            self.cursor = None
        def add_image_from_path(self, path, contains_human=0):
            self.add_image(Application.ImageData.from_file(path, contains_human))
        def add_image(self, data):
            try:
                self.cursor.execute('''INSERT INTO images
                                    (id, img, time_stamp, contains_human) 
                                    VALUES (?, ?, ?, ?);''',
                              [data.ID,
                               data.serialize(),
                               data.timestamp,
                               data.contains_human])
                self.connection.commit()
            except sqlite3.IntegrityError:
                self.update_image(data)
        def update_image(self, data):
            self.cursor.execute('''UPDATE images
                              SET contains_human = ?
                              WHERE id = ?;''',
                            (data.contains_human, data.ID))
            self.connection.commit()
        def delete_image(self, data):
            print("Deleting image of ID {}".format(data.ID))
            self.cursor.execute('''DELETE from
                                images
                                WHERE
                                id = '{}';'''.format(data.ID))
            self.connection.commit()
        def query_database(self, contains_human = None):
            conditions = []
            if contains_human is not None:
                conditions.append("(contains_human = {})".format(contains_human))
            query = '''SELECT *
            FROM images
            
            '''
            if len(conditions) > 0:
                query += 'WHERE '
                for c in conditions[:-1]:
                    query += c
                    query += ' AND '
                query += conditions[-1]
            query += ';'
            print('QUERY:')
            print(query)
            self.cursor.execute(query)
            images = []
            for i in self.cursor:
                images.append(Application.ImageData.from_database(i[0], i[1], i[2], i[3]))
            return images
        def dump_all_images(self):
            self.cursor.execute('''SELECT img FROM images;''')
            images = []
            for i in self.cursor:
                image  = Application.ImageData.from_database(i[0], i[1], i[2], i[3])
                images.append(image.image)
            for i in range(1, len(images) + 1):
                cv.imwrite('OUTPUT/IMGDUMP - {}.png'.format(i), images[i-1])
        
    class AdminInterface:
        '''
        Provides a Graphical User Interface for the System Administrator.
        
        The System Administrator is not necessarily a priviliged user, but
        rather a user with a different role from the System Monitor.  This
        user could just as appropriately be referred to as "System Maintenance"
        '''
        def __init__(self):
            self.edit_image_window_sem = BoundedSemaphore()
            '''
            Initializes the "Admin" Panel.
            '''
            def on_close(this):
                this.root.destroy()
                if this.database is not None:
                    this.database.close_database()
            self.database = Application.Database()
            self.root  = tk.Tk()
            self.toplevel = tk.LabelFrame(master=self.root,
                                     text  = 'Main Panel',
                                     padx  = 5,
                                     pady  = 5)
            self.toplevel.pack(side = tk.TOP)
            info_frame = tk.LabelFrame(master = self.toplevel,
                                     text  = 'Information')
            info_frame.pack(side = tk.LEFT, expand = 1, fill = tk.BOTH)
            tk.Label(master = info_frame,
                     text = 'Mrs. Drone - Administration System').pack(side = tk.TOP, expand = 1, fill = tk.X)
            tk.Label(master = info_frame, 
                     text = 'Version: Beta 0.2').pack(side = tk.TOP, expand = 1, fill = tk.X)
            self.database_label = tk.StringVar(master = info_frame,
                                               value = 'N/A')
            tk.Label(master = info_frame,
                     textvariable = self.database_label).pack(side = tk.TOP, expand = 1, fill = tk.X)
            button_panel = tk.LabelFrame(master = self.toplevel,
                                     text  = 'Controls',
                                     padx  = 5,
                                     pady  = 5)
            button_panel.pack(side = tk.LEFT, expand = 1, fill = tk.X)
            button_args = [('New Database', self.__new_database_dialog),
                           ('Open Database', self.__open_database_dialog),
                           ('Add Images', self.__add_images_dialog),
                           ('Query Database', self.__query_database_window),
                           ('Exit', partial(on_close, self))]
            self.top_level_commands = []
            for b in button_args:
                self.top_level_commands.append(tk.Button(master = button_panel,
                          text   = b[0],
                          command= b[1]))
                self.top_level_commands[-1].pack(side = tk.TOP, expand = 1, fill = tk.X)
            self.action_frame = None
            self.__init_action_frame()
            self.image_frame = None
            self.__init_image_frame()
            
            tk.mainloop()
        #Did not use a semaphore here because this is more about showing the user
        #which commands are available, rather than controlling timing with the system.
        def __lock_top_level_commands(self):
            for c in self.top_level_commands:
                c.config(state=tk.DISABLED)
        def __unlock_top_level_commands(self):
            for c in self.top_level_commands:
                c.config(state=tk.NORMAL)
        def __init_action_frame(self, text = "None"):
            if self.action_frame is not None:
                self.action_frame.destroy()
            self.action_frame = tk.LabelFrame(master=self.toplevel,
                                              text  = "Current Action - {}".format(text),
                                              padx  = 5,
                                              pady  = 5)
            self.action_frame.pack(side = tk.RIGHT, expand = 1, fill = tk.BOTH)
        def __init_image_frame(self, text = "None"):
            if self.image_frame is not None:
                self.image_frame.destroy()
            self.image_frame = tk.LabelFrame(master=self.root,
                                              text  = "Image Manipulation Frame".format(text),
                                              padx  = 5,
                                              pady  = 5)
            self.image_frame.pack(expand = 1, fill = tk.BOTH)
            self.image_view = VerticalScrolledFrame(parent=self.image_frame)
            self.image_view.pack(expand = 1, fill = tk.BOTH)
        def __new_database_dialog(self):
            options = {}
            options['defaultextension'] = '.sqlite3'
            options['filetypes'] = [('SQLite3 Database', '.sqlite3')]
            options['initialfile']      = 'new.sqlite3'
            options['title']            = 'New Database'
            path = filedialog.asksaveasfilename(**options)
            if len(path) > 0 and not os.path.exists(path):
                self.database_label.set(path)
                return self.database.open_database(path)
            return None
        def __open_database_dialog(self):
            options = {}
            options['defaultextension'] = '.sqlite3'
            options['filetypes'] = [('SQLite3 Database', '.sqlite3')]
            options['title']            = 'Open Database'
            path = filedialog.askopenfilename(**options)
            if len(path) > 0:
                self.database_label.set(path)
                return self.database.open_database(path)
            return None
        def __add_images_dialog(self):
            if not self.database.is_open():
                return
            self.__init_action_frame(text = "Add Images to the Database")
            master = self.action_frame
            def on_close():
                self.__init_action_frame()
                self.__unlock_top_level_commands()
            def select_images(mode):
                if len(mode.curselection()) == 0:
                    return
                mode = mode.curselection()[0]
                options = {}
                options['defaultextension'] = '.sqlite3'
                options['title']            = 'Open Database'
                options['filetypes']        = [('FORMAT', '.jpg')]
                paths = filedialog.askopenfilenames(**options)
                on_close()
                print(mode)
                total = len(paths) + 1
                i = 1
                if mode == 0:
                    for p in paths:
                        print('Adding image {} of {}.'.format(i, total))
                        i += 1
                        img = Application.ImageData.from_file(path=p, contains_human=1)
                        self.__update_database(img, 1)
                elif mode == 1:
                    for p in paths:
                        print('Adding image {} of {}.'.format(i, total))
                        i += 1
                        img = Application.ImageData.from_file(path=p, contains_human=0)
                        self.__update_database(img, 0)
                else:
                    for p in paths:
                        img = Application.ImageData.from_file(path=p)
                        self.__edit_image_window(img, master=master)
                        
            mode = tk.Listbox(master = master,
                              selectmode=tk.SINGLE)
            mode.insert(0, 
                        'Images contain a human',
                        'Images do not contain humans',
                        'Ask whether each image contains a human')
            mode.config(width=0)
            mode.pack(side = tk.LEFT, expand = 1, fill = tk.BOTH)
            tk.Button(master = master,
                      text = 'Select images',
                      command = partial(select_images,
                                        mode)).pack(side = tk.LEFT, expand = 1, fill = tk.BOTH)
            tk.Button(master = master,
                      text = 'Cancel',
                      command = on_close).pack(side = tk.LEFT, expand = 1, fill = tk.BOTH)
            self.__lock_top_level_commands()
        def __update_database(self, data, contains_human):
            data.update(contains_human)
            self.database.cursor.execute('''SELECT * FROM images WHERE id = "{}"'''.format(data.ID))
            if self.database.cursor.fetchone() is not None:
                self.database.update_image(data)
            else:
                self.database.add_image(data)
        def __delete_image(self, data):
            self.database.delete_image(data)
        def __query_database(self, contains_human_widget=None):
            if contains_human_widget is not None:
                contains_human_options = {0 : 1,
                                      1 : 0,
                                      2 : None}
                human = contains_human_options[contains_human_widget.curselection()[0]]
            else:
                human = None
            result = self.database.query_database(
                    contains_human = human)
            self.__init_image_frame()
            self.query = {}
            def delete_callback(f, image):
                self.__delete_image(image)
                f.destroy()
            def update_callback(image, contains_human):
                image.contains_human = contains_human
                self.__update_database(image, contains_human)
                if image.contains_human:
                    self.query[image.ID]['contains_human_var'].set('Contains a human.')
                else:
                    self.query[image.ID]['contains_human_var'].set('Does not contain a human.') 
            for image in result:
                f = tk.Frame(master = self.image_view.interior)
                f.data = image
                f.pack(side = tk.TOP)
                self.query[image.ID] = {'frame' : f,
                          'timestamp'           : image.timestamp,
                          'contains_human_var'  : tk.StringVar(master=f)}
                if image.contains_human:
                    self.query[image.ID]['contains_human_var'].set('Contains a human.')
                else:
                    self.query[image.ID]['contains_human_var'].set('Does not contain a human.')
                b,g,r = cv.split(image.image)
                tk_image = ImageTk.PhotoImage(Image.fromarray(cv.merge((r,g,b))))
                label = tk.Label(master = f, image = tk_image)
                label.image = tk_image
                label.pack(side = tk.LEFT)
                controls = tk.Frame(master = f)
                controls.pack(side=tk.RIGHT, expand=1, fill=tk.BOTH)
                tk.Label(master = controls, text = 'ID - {}'.format(image.ID)).pack(side=tk.TOP)
                tk.Label(master = controls, text = 'Timestamp - {}'.format(image.timestamp)).pack(side=tk.TOP)
                tk.Label(master = controls, 
                         textvariable = self.query[image.ID]['contains_human_var']).pack(side=tk.TOP)
                tk.Button(master=controls,
                          text = 'SET - Image contains a human',
                          command = partial(update_callback, f.data, 1)).pack(side = tk.TOP, expand = 1, fill = tk.X)
                tk.Button(master=controls,
                          text = 'SET - Image does not contain a human',
                          command = partial(update_callback, f.data, 0)).pack(side = tk.TOP, expand = 1, fill = tk.X)
                tk.Button(master=controls,
                          text = 'Delete',
                          command = partial(delete_callback, f, image)).pack(side = tk.TOP, expand = 1, fill = tk.X)
                tk.Button(master=controls,
                          text = 'Dismiss',
                          command = partial(f.destroy)).pack(side = tk.TOP, expand = 1, fill = tk.X)
        def __query_database_window(self):
            if not self.database.is_open():
                return
            self.__init_action_frame(text = "Query Database")
            master = self.action_frame
            def on_close():
                self.__init_action_frame()
                self.__unlock_top_level_commands()
            def select_all():
                msg = '''Warning: Do not use the Select All operation on large databases.
                Are you sure you want to proceed?
                '''
                if not messagebox.askokcancel(title = 'Warning', message = msg, icon = tk.messagebox.WARNING):
                    return
                print('getting results')
                self.__query_database()
            controls = tk.LabelFrame(master = master,
                                     text   = 'Controls', 
                                     padx   = 5,
                                     pady   = 5)
            controls.pack(side = tk.TOP, expand = 1, fill = tk.X)
            contains_human_frame = tk.Frame(master = controls)
            contains_human_frame.pack(side = tk.LEFT)
            contains_human = tk.Listbox(master = controls,
                              selectmode=tk.SINGLE)
            contains_human.insert(0, 
                        'Retrieve only images which contain humans.',
                        'Retrieve only images which do not contain humans.',
                        'Retrieve images regardless of whether they contain humans.')
            contains_human.config(width=0)
            contains_human.pack(side = tk.TOP)
            
            timestamp_frame = tk.LabelFrame(master = controls,
                                     text   = 'Image Timestamp Range', 
                                     padx   = 5,
                                     pady   = 5)
            tk.Label(master = timestamp_frame,
                     text   = 'TODO - query database by timestamp range')
            
            
            tk.Button(master = controls,
                      text = "Retrieve All Images from Database",
                      command = select_all).pack(side = tk.LEFT, expand = 1, fill = tk.BOTH)
            
            tk.Button(master = controls,
                      text = "Retrieve Images which meet given criteria",
                      command = partial(self.__query_database,
                                        contains_human)).pack(side = tk.LEFT, expand = 1, fill = tk.BOTH)
            
            
            tk.Button(master = controls,
                      text = 'Exit',
                      command = on_close).pack(side = tk.RIGHT, expand = 1, fill = tk.BOTH)
            self.__lock_top_level_commands()
        def __edit_image_window(self, data, master=None):
            print("Called")
            #self.edit_image_window_sem.acquire(blocking=True)
            if master is None:
                master = self.root
            def on_close():
                popup.destroy()
                #self.edit_image_window_sem.release()
            #I'm sorry to anyone who has to read the code of this function...
            #TODO - Clean up this function to remove the need for a popup window, and also
            def on_confirm():
               self. __update_database(data, result.get())
               on_close()
            popup = tk.Toplevel(master = self.root)
            m = tk.PanedWindow(master = popup)
            m.pack(fill = tk.BOTH, expand = 1)
        
            b,g,r = cv.split(data.image)   #Credit - Iony at https://stackoverflow.com/questions/28670461/read-an-image-with-opencv-and-display-it-with-tkinter
            tk_image    = ImageTk.PhotoImage(Image.fromarray(cv.merge((r,g,b))))
            left        = tk.Label(m, image = tk_image)
            left.image  = tk_image
            left.pack()
            m.add(left)
            
            right       = tk.PanedWindow(m, orient = tk.VERTICAL)
            right.pack()
            
            hash_frame  = tk.PanedWindow(right, orient = tk.HORIZONTAL)
            hash_frame.pack()
            hash_frame1 = tk.Label(hash_frame, text = "Image ID: ")
            hash_frame2 = tk.Label(hash_frame, text = data.ID)
            hash_frame.add(hash_frame1)
            hash_frame.add(hash_frame2)
            
            right.add(hash_frame)
            
            time_frame  = tk.PanedWindow(right, orient = tk.HORIZONTAL)
            time_frame.pack()
            time_frame1 = tk.Label(time_frame, text = "Timestamp: ")
            time_frame2 = tk.Label(time_frame, text = data.timestamp)
            time_frame.add(time_frame1)
            time_frame.add(time_frame2)
            
            right.add(time_frame)
            
            bool_frame  = tk.PanedWindow(right, orient = tk.HORIZONTAL)
            bool_frame.pack()
            bool_frame1 = tk.Label(bool_frame, text = 'Image contains a human:')
            bool_frame2 = tk.PanedWindow(bool_frame, orient = tk.VERTICAL)
            bool_frame2.pack()
            result = tk.BooleanVar(bool_frame)
            has_human = tk.Radiobutton(master   = bool_frame2, 
                                       text     = "Yes",
                                       variable = result,
                                       value = 1,
                                       state    = tk.NORMAL)
            no_human  = tk.Radiobutton(master   = bool_frame2, 
                                       text     = "No",
                                       variable = result,
                                       value = 0,
                                       state    = tk.NORMAL)

        
            bool_frame2.add(has_human)
            bool_frame2.add(no_human)
        
            bool_frame.add(bool_frame1)
            bool_frame.add(bool_frame2)
            right.add(bool_frame)
        
            confirm_button = tk.Button(master  = right,
                                       text    = 'Confirm',
                                       command = on_confirm)
            right.add(confirm_button)
            m.add(right)
        
x = Application.AdminInterface()
'''
DEPRECATED, old main method from dbPrototype.bak

def main():
    db = open_database('blake.db')
    c = db.cursor()
    for image in os.listdir('INPUT'):
        add_img_from_path(c, 'INPUT/' + image)
        db.commit()
    db.close()

#if __name__ == '__main__': main()
'''