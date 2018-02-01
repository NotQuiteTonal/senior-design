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
            self.image_frame.pack(side = tk.BOTTOM, expand = 1, fill = tk.BOTH)
            self.image_canvas = tk.Canvas(master = self.image_frame)
            self.image_canvas.grid()
            vbar = tk.Scrollbar(master = self.image_canvas, orient = tk.VERTICAL)
            vbar.pack(side = tk.RIGHT, fill = tk.Y)
            vbar.config(command = self.image_canvas.yview)
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
                if mode == 0:
                    for p in paths:
                        img = Application.ImageData.from_file(path=p, contains_human=1)
                        self.database.update_image(img)
                elif mode == 1:
                    for p in paths:
                        img = Application.ImageData.from_file(path=p, contains_human=0)
                        self.database.update_image(img)
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
        def __query_database_window(self):
            if not self.database.is_open():
                return
            self.__init_action_frame(text = "Query Database")
            master = self.action_frame
            def on_close():
                self.__init_action_frame()
                self.__unlock_top_level_commands()
            def query():
                result = self.database.query_database()
                
                self.__init_image_frame()
                
                for image in result:
                    f = tk.Frame(master = self.image_canvas)
                    f.pack(side = tk.TOP)
                    b,g,r = cv.split(image.image)
                    tk_image = ImageTk.PhotoImage(Image.fromarray(cv.merge((r,g,b))))
                    label = tk.Label(master = f, image = tk_image)
                    label.image = tk_image
                    label.pack(side = tk.LEFT)
                    
            def select_all():
                msg = '''Warning: Do not use the Select All operation on large databases.
                Are you sure you want to proceed?
                '''
                if not messagebox.askokcancel(title = 'Warning', message = msg, icon = tk.messagebox.WARNING):
                    return
                print('getting results')
                query()
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
            
            
            tk.Button(master = controls,
                      text = "Retrieve All Images from Database",
                      command = select_all).pack(side = tk.LEFT, expand = 1, fill = tk.BOTH)
            tk.Button(master = controls,
                      text = 'Exit',
                      command = on_close).pack(side = tk.RIGHT, expand = 1, fill = tk.BOTH)

            
            images = tk.LabelFrame(master   = master,
                                   text     = 'Images Found',
                                   padx     = 5,
                                   pady     = 5)
            images.pack(side = tk.BOTTOM, expand = 1, fill = tk.BOTH)
            
            self.queried_images = []
            
        def __edit_image_window(self, data, master=None):
            if master is None:
                master = self.root
            def on_close():
                popup.destroy()
                self.root.deiconfiy()
            #I'm sorry to anyone who has to read the code of this function...
            #TODO - Clean up this function to remove the need for a popup window, and also
            def on_confirm():
               self. __update_database(data, result.get())
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