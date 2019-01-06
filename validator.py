# -*- coding:utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        标注审核工具
# Author:      xingoo
# Created:     2019-01-05
# -------------------------------------------------------------------------------
from __future__ import division
from tkinter import *
from PIL import Image, ImageTk
import os
import glob
import json
import xlrd
import xlwt
import tkinter.messagebox as msgbox

w0 = 1  # 图片原始宽度
h0 = 1  # 图片原始高度

# 指定缩放后的图像大小
DEST_SIZE = 600, 900

# 图片状态
LABEL_IMG_STATUS_NORMAL = '正常'
LABEL_IMG_STATUS_UNNORMAL = '倾斜/模糊'
LABEL_IMG_STATUS_WRONG = '有问题'
LABEL_IMG_STATUS_OTHER = '未确认'

COLOR_BLUE = 'blue'
COLOR_RED = 'red'
COLOR_YELLOW = 'yellow'
COLOR_GREEN = 'green'
COLOR_BLACK = 'black'

class LabelTool(Tk):
    def __init__(self):
        super().__init__()
        self.title("标注校验工具")

        self.frame = Frame(self)
        self.frame.pack(fill=BOTH, expand=1)
        self.resizable(width=TRUE, height=TRUE)

        self.cur = 0
        self.total = 0
        self.tkimg = None

        # reference to bbox
        self.bboxIdList = []
        self.bboxId = None
        self.bboxList = []
        self.hl = None
        self.vl = None

        # 自己标注的变量
        self.customer_labels = []
        self.customer_boxes = []
        self.customer_boxes_cur = None
        # 针对图片的校对信息，通常是在有问题的时候进行说明
        self.label_text_info = StringVar()
        # 保存当前全部图片的校对信息
        self.result = []
        # 当前图片的校对信息
        self.status = None

        # ----------------- GUI stuff ---------------------
        # 图片目录和标注信息目录
        self.imageLabel = Label(self.frame, text="图片目录:")
        self.imageLabel.grid(row=0, column=0, sticky=E)
        self.imageEntry = Entry(self.frame)
        self.imageEntry.grid(row=0, column=1, sticky=W + E)

        self.jsonLabel = Label(self.frame, text="标注目录")
        self.jsonLabel.grid(row=1, column=0, sticky=E)
        self.jsonEntry = Entry(self.frame)
        self.jsonEntry.grid(row=1, column=1, sticky=W + E)

        self.ldBtn = Button(self.frame, text="加载", font=("微软雅黑", 15, 'bold'), command=self.load)
        self.ldBtn.grid(row=0, column=2, rowspan=2, sticky=W + E + N + S)

        # main panel for labeling
        self.mainPanel = Canvas(self.frame, cursor='tcross')
        self.mainPanel.bind("<Motion>", self.mouseMove)
        self.mainPanel.grid(row=2, column=1, rowspan=4, sticky=W + N)

        self.infoEntry = Entry(self.frame, textvariable=self.label_text_info, font=("微软雅黑", 15, 'bold'))
        self.infoEntry.grid(row=6, column=1, sticky=W + N + E + S)
        self.infoEntry.bind("<FocusOut>", self.update_status)

        # showing bbox info & delete bbox
        self.lb1 = Label(self.frame, text='标注内容:')
        self.lb1.grid(row=2, column=2, sticky=W + N)

        self.listbox = Listbox(self.frame, width=40, height=30, font=("微软雅黑", 14))
        self.listbox.grid(row=3, column=2, sticky=W + E + N)

        self.btnNormal = Button(self.frame, text='正常', font=("微软雅黑", 15, 'bold'), height=2, fg='blue', command=self.normal)
        self.btnNormal.grid(row=4, column=2, sticky=W + E)
        self.btnUnNormal = Button(self.frame, text='倾斜/模糊', font=("微软雅黑", 15, 'bold'), height=2, fg='blue', command=self.unnormal)
        self.btnUnNormal.grid(row=5, column=2, sticky=W + E)
        self.btnWrong = Button(self.frame, text='有问题', font=("微软雅黑", 15, 'bold'), height=2, fg='blue', command=self.wrong)
        self.btnWrong.grid(row=6, column=2, sticky=W + E)

        # control panel for image navigation
        self.ctrPanel = Frame(self.frame)
        self.ctrPanel.grid(row=7, column=1, columnspan=2, sticky=W + E)
        self.prevBtn = Button(self.ctrPanel, text='<< 前一张', font=("微软雅黑", 15, 'bold'), width=20, height=2, command=self.prevImage)
        self.prevBtn.pack(side=LEFT, padx=5, pady=3)
        self.nextBtn = Button(self.ctrPanel, text='下一张 >>', font=("微软雅黑", 15, 'bold'), width=20, height=2, command=self.nextImage)
        self.nextBtn.pack(side=LEFT, padx=5, pady=3)
        self.progLabel = Label(self.ctrPanel, text="Progress:     /    ")
        self.progLabel.pack(side=LEFT, padx=5)

        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(4, weight=1)

    def decorator_btn(self):
        """
        修改三种状态按钮的样式
        :return:
        """
        if self.status == LABEL_IMG_STATUS_NORMAL:
            self.btnNormal['fg'] = COLOR_RED
            self.btnUnNormal['fg'] = COLOR_BLUE
            self.btnWrong['fg'] = COLOR_BLUE
        elif self.status == LABEL_IMG_STATUS_UNNORMAL:
            self.btnNormal['fg'] = COLOR_BLUE
            self.btnUnNormal['fg'] = COLOR_RED
            self.btnWrong['fg'] = COLOR_BLUE
        elif self.status == LABEL_IMG_STATUS_WRONG:
            self.btnNormal['fg'] = COLOR_BLUE
            self.btnUnNormal['fg'] = COLOR_BLUE
            self.btnWrong['fg'] = COLOR_RED
        else:
            self.btnNormal['fg'] = COLOR_BLUE
            self.btnUnNormal['fg'] = COLOR_BLUE
            self.btnWrong['fg'] = COLOR_BLUE

    def update_status(self, event=None):
        """
        更新图片按钮：
        1 修改按钮状态颜色
        2 修改result中的信息
        3 保存到excel
        :return:
        """
        # 更新按钮状态
        self.decorator_btn()

        # 更新self.result内容，更新状态和描述信息
        self.result[self.cur - 1][1] = self.status
        self.result[self.cur - 1][2] = self.label_text_info.get()

        # 保存到excel
        self.save_excel()

    def normal(self):
        self.status = LABEL_IMG_STATUS_NORMAL
        self.nextImage()

    def unnormal(self):
        self.status = LABEL_IMG_STATUS_UNNORMAL
        self.nextImage()

    def wrong(self):
        self.status = LABEL_IMG_STATUS_WRONG
        self.infoEntry.icursor(END)
        self.update_status()

    def save_excel(self):
        """
        保存到excel
        :return:
        """
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('sheet1')

        # TODO 样式待定
        title_style = xlwt.XFStyle()  # 初始化样式
        pattern = xlwt.Pattern()  # Create the Pattern
        # May be: NO_PATTERN, SOLID_PATTERN, or 0x00 through 0x12
        pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        # May be:
        # 8 through 63.
        # 0 = Black, 1 = White, 2 = Red, 3 = Green, 4 = Blue, 5 = Yellow, 6 = Magenta, 7 = Cyan,
        # 16 = Maroon, 17 = Dark Green, 18 = Dark Blue, 19 = Dark Yellow , almost brown),
        # 20 = Dark Magenta, 21 = Teal, 22 = Light Gray, 23 = Dark Gray, the list goes on...
        pattern.pattern_fore_colour = 3
        title_style.pattern = pattern

        worksheet.write(0, 0, '图片', title_style)
        worksheet.write(0, 1, '结果', title_style)
        worksheet.write(0, 2, '提示', title_style)

        body_style = xlwt.XFStyle()
        for i, c in enumerate(self.result):

            if c[1] == LABEL_IMG_STATUS_WRONG:
                pattern = xlwt.Pattern()
                pattern.pattern_fore_colour = 2
                body_style.pattern = pattern
            elif c[1] == LABEL_IMG_STATUS_UNNORMAL:
                pattern = xlwt.Pattern()
                pattern.pattern_fore_colour = 5
                body_style.pattern = pattern

            worksheet.write(i + 1, 0, c[0], body_style)
            worksheet.write(i + 1, 1, c[1], body_style)
            worksheet.write(i + 1, 2, c[2], body_style)

        workbook.save(self.excel_path)

    def load_excel(self):
        """
        加载excel
        :return:
        """
        if os.path.exists(self.excel_path):
            data = xlrd.open_workbook(self.excel_path, encoding_override='utf-8')
            table = data.sheets()[0]
            nrows = table.nrows
            # 忽略第一行内容

            cache_map = {}
            for i in range(1, nrows):
                cache_map[table.cell_value(i, 0)] = [table.cell_value(i, 1), table.cell_value(i, 2)]

            for name, _, _ in self.customer_labels:
                self.result.append([name, cache_map[name][0], cache_map[name][1]])
        else:
            for name, _, _ in self.customer_labels:
                self.result.append([name, LABEL_IMG_STATUS_OTHER, ''])

    def load(self):
        image_path = self.imageEntry.get()
        json_path = self.jsonEntry.get()

        self.excel_path = os.path.join(image_path, '%s.xls' % os.path.basename(image_path))

        # 检查目录是否正确
        if not os.path.exists(image_path):
            msgbox.showinfo('提示', "目录[%s]不存在" % image_path)
            return

        if not os.path.exists(json_path):
            msgbox.showinfo('提示', "目录[%s]不存在" % json_path)
            return

        self.load_image_and_json(image_path, json_path)
        self.cur = 1
        self.load_excel()
        self.total = len(self.customer_labels)
        self.load_images()

    def load_image_and_json(self, image_base_path, json_base_path):
        """
        遍历图片，寻找对应的json信息。如果有标注的，则插入到前面；如果没有标注的则放在后面
        :param image_path:
        :param json_path:
        :return:
        """
        self.customer_labels = []

        # 校验能否对的上?
        for image_path in glob.glob(os.path.join(image_base_path, "*.jpg")):
            _, image_name = os.path.split(image_path)
            prefix = str(image_name.split('_')[0])+'_'
            json_files = glob.glob(os.path.join(json_base_path, prefix+'*.json'))

            json_name = image_name.replace('.jpg', '.json')
            json_path = os.path.join(json_base_path, json_name)
            json_dict = None

            if len(json_files) > 0:
                json_path = json_files[0]

            if not os.path.exists(json_path):
                # 有可能是因为图片倾斜没有进行标注
                print('找不到图片【%s】对应的标注文件【%s】' % (image_name, json_name))
                msgbox.showerror('提示', '找不到图片【%s】对应的标注文件【%s】' % (image_name, json_name))
            else:
                with open(json_path, "r", encoding='utf-8') as load_f:
                    json_dict = json.load(load_f)

            if json_dict is None or 'outputs' not in json_dict or len(json_dict['outputs']) == 0:
                self.customer_labels.append((image_name, image_path, json_dict))
            else:
                self.customer_labels.insert(0, (image_name, image_path, json_dict))

    def load_images(self):
        # 加载图片
        self.img_name, self.img_path, self.img_dict = self.customer_labels[self.cur - 1]
        pil_image = Image.open(self.img_path)

        global w0, h0
        w0, h0 = pil_image.size

        pil_image = pil_image.resize((DEST_SIZE[0], DEST_SIZE[1]), Image.ANTIALIAS)
        global w1, h1
        w1, h1 = pil_image.size

        self.img = pil_image
        self.tkimg = ImageTk.PhotoImage(pil_image)
        self.mainPanel.config(width=max(self.tkimg.width(), 400), height=max(self.tkimg.height(), 400))
        self.mainPanel.create_image(0, 0, image=self.tkimg, anchor=NW)
        self.progLabel.config(text="%04d/%04d" % (self.cur, self.total))

        # 加载状态
        self.status = self.result[self.cur - 1][1]
        self.label_text_info.set(self.result[self.cur - 1][2])

        # 更新状态
        self.decorator_btn()

        # 更新文本框列表
        self.decorator()

    def decorator(self):
        self.clearBBox()
        if self.img_dict is not None and 'outputs' in self.img_dict and 'object' in self.img_dict['outputs']:
            for (i, line) in enumerate(self.img_dict['outputs']['object']):
                text = line['name']
                bndbox = line['bndbox']

                # 读取原始坐标，并进行转换
                x1 = (bndbox['xmin'] / w0) * w1
                y1 = (bndbox['ymin'] / h0) * h1
                x2 = (bndbox['xmax'] / w0) * w1
                y2 = (bndbox['ymax'] / h0) * h1

                self.customer_boxes.append((x1, y1, x2, y2))

                if i == self.customer_boxes_cur:
                    self.bboxIdList.append(self.mainPanel.create_rectangle(x1, y1, x2, y2, width=4, outline=COLOR_BLUE))
                    self.listbox.insert(END, text)
                    self.listbox.itemconfig(len(self.bboxIdList) - 1, fg=COLOR_BLUE)
                else:
                    self.bboxIdList.append(self.mainPanel.create_rectangle(x1, y1, x2, y2, width=2, outline=COLOR_GREEN))
                    self.listbox.insert(END, text)
                    self.listbox.itemconfig(len(self.bboxIdList) - 1, fg=COLOR_BLACK)

    def mouseMove(self, event):
        self.customer_boxes_cur = None

        for i, (x1, y1, x2, y2) in enumerate(self.customer_boxes):
            if x2 >= event.x >= x1 and y2 >= event.y >= y1:
                if i != self.customer_boxes_cur:
                    self.customer_boxes_cur = i
                    self.decorator()
                break

        if self.tkimg:
            if self.hl:
                self.mainPanel.delete(self.hl)
            self.hl = self.mainPanel.create_line(0, event.y, self.tkimg.width(), event.y, width=2, fill=COLOR_YELLOW, dash=(4, 4))
            if self.vl:
                self.mainPanel.delete(self.vl)
            self.vl = self.mainPanel.create_line(event.x, 0, event.x, self.tkimg.height(), width=2, fill=COLOR_YELLOW, dash=(4, 4))

    def clearBBox(self):
        for idx in range(len(self.bboxIdList)):
            self.mainPanel.delete(self.bboxIdList[idx])
        self.listbox.delete(0, len(self.bboxIdList))
        self.bboxIdList = []
        self.customer_boxes = []

    def prevImage(self, event=None):
        self.update_status()
        if self.cur > 1:
            self.cur -= 1
            self.load_images()

    def nextImage(self, event=None):
        self.update_status()
        if self.cur < self.total:
            self.cur += 1
            self.load_images()

if __name__ == '__main__':
    tool = LabelTool()
    tool.mainloop()
