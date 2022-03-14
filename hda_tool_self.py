import sys, os, json
import wx
import wx.lib.agw.floatspin as FS
import wx.lib.scrolledpanel
from wx import glcanvas
from OpenGL.GL import *
import OpenGL.GL.shaders
import numpy
from pyrr import Matrix44
import time

global slider_value
slider_value = []


vertex_shader = """
# version 330
in layout(location = 0) vec3 positions;
in layout(location = 1) vec3 colors;

out vec3 newColor;
uniform mat4 model;

void main(){
    gl_Position = model * vec4(positions, 1.0);
    newColor = colors;
}
"""

fragment_shader = """
# version 330

in vec3 newColor;
out vec4 outColor;

void main(){
    outColor = vec4(newColor, 1.0);
}

"""

#import the houdini library
def enableHouModule():
    if hasattr(sys, "setdlopenflags"):
        old_dlopen_flags = sys.getdlopenflags()
        import DLFCN
        sys.setdlopenflags(old_dlopen_flags | DLFCN.RTLD_GLOBAL)

    try:
        import hou
    except ImportError:
        # Add $HFS/houdini/python2.7libs to sys.path so Python can find the
        # hou module.
        sys.path.append("C:/Program Files/Side Effects Software/Houdini 19.0.498/houdini/python%d.%dlibs" % sys.version_info[:2])
        import hou
    finally:
        if hasattr(sys, "setdlopenflags"):
            sys.setdlopenflags(old_dlopen_flags)

#find all the multiparamteres in the root folder and add to an array
def allParmTemplates(group):
    for parm_template in group.parmTemplates():
        if parm_template.type() == hou.parmTemplateType.Folder:
            if parm_template.folderType() == hou.folderType.MultiparmBlock:
                multiparms.append(parm_template)
            allParmTemplates(parm_template)
            
class OpenGLCanvas(glcanvas.GLCanvas):
    def __init__(self, parent):
        glcanvas.GLCanvas.__init__(self, parent, -1, size = (400,500))
        self.init = False
        self.context = glcanvas.GLContext(self)
        self.SetCurrent(self.context)
        self.rotate = False
        self.rot_y = Matrix44.identity()
        
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnResize)

    def OnResize(self, event):
        size = self.GetClientSize()
        glVewport(0, 0, size.width, size.height)
        self.canvas.Refresh()

    def OnPaint(self, event):
        wx.PaintDC(self)
        if not self.init:
            self.InitGL()
            self.init = True
        self.OnDraw()

    def InitGL(self):
        #verticies  vert pos     vert colors
        triangle = ([-0.5,-0.5,0.0, 1.0,0.0,0.0,
                     0.5,-0.5,0.0, 0.0,1.0,0.0,
                     0.0,0.5,0.0, 0.0,0.0,1.0])

        #need to convert to numpy array for OpenGL, python array will not do
        triangle = numpy.array(triangle, dtype=numpy.float32)

        shader = OpenGL.GL.shaders.compileProgram(OpenGL.GL.shaders.compileShader(vertex_shader, GL_VERTEX_SHADER),
                                                  OpenGL.GL.shaders.compileShader(fragment_shader, GL_FRAGMENT_SHADER))

        #vertex buffer object
        vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        #2nd argument, how many bytes(6*3 =18, 18*4= 72)
        glBufferData(GL_ARRAY_BUFFER, len(triangle)*4, triangle, GL_STATIC_DRAW)

        #layout location(long string at beginning, 3 values for each vert, type of value, normalize, stride (6 values (loc and color) *4), offset
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)

        #offset is 12 bc 3*4 = 12, 3 values for location
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)

        glClearColor(0.1, 0.15, 0.1, 1.0)

        glUseProgram(shader)

        self.model_loc = glGetUniformLocation(shader, "model")
    
    #override OnDraw
    def OnDraw(self):
        glClear(GL_COLOR_BUFFER_BIT)

        if self.rotate:
            ct = time.process_time()
            self.rot_y = Matrix44.from_y_rotation(ct)
            glUniformMatrix4fv(self.model_loc, 1, GL_FALSE, self.rot_y)
            self.Refresh()
        else:
            glUniformMatrix4fv(self.model_loc, 1, GL_FALSE, self.rot_y)
            
        #start with which element, how many vertext tp draw
        glDrawArrays(GL_TRIANGLES, 0, 3)
        self.SwapBuffers()

    
class MainPanel(wx.ScrolledWindow):
    def __init__(self, parent):
        wx.ScrolledWindow.__init__(self, parent=parent, id=wx.ID_ANY)
        self.SetScrollbars(1, 1, 1, 1, noRefresh=False)
        self.Layout()
        self.SetSize(450, 700)

class GLPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent=parent)
        self.canvas = OpenGLCanvas(self)

        self.rot_btn=wx.Button(self, -1, label="Start/Stop\nrotation", pos=(410, 10), size=(100, 50))
        self.rot_btn.BackgroundColour = [125,125,125]
        self.rot_btn.ForegroundColour = [255,255,255]

        self.rot_btn.Bind(wx.EVT_BUTTON, self.rotate)

    def rotate(self, event):
        if not self.canvas.rotate:
            self.canvas.rotate = True
            self.canvas.Refresh()
        else:
            self.canvas.rotate = False
        

class Mywin(wx.Frame): 
    def __init__(self, parent, title): 

        screenSize = wx.DisplaySize()
        screenWidth = screenSize[0]
        screenHeight = screenSize[1]

        super(Mywin, self).__init__(parent, title = title,size = (1100,700))

        self.Bind(wx.EVT_CLOSE, self.onClose)

        #import houdini capabilities
        enableHouModule()
        import hou  

        #set up infrustructure for window
        self.main_splitter = wx.SplitterWindow(self)
        self.panel = MainPanel(self.main_splitter)        

        self.vbox_labels = wx.BoxSizer(wx.VERTICAL)
        self.vbox_values = wx.BoxSizer(wx.VERTICAL)
        self.hbox_main = wx.BoxSizer(wx.HORIZONTAL)
        self.vbox_labels.AddSpacer(5)
        
        #find path to HDA
        l1 = wx.StaticText(self.panel, -1, "HDA Path")

        wildcard = "Houdini Digital Asset (*.hda; *.hdalc)|*.hda;*hdalc|" \
                   "All files (*.*)|*.*"
        self.vbox_labels.Add(l1, 1, wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,5)
        self.path_to_hda = wx.FilePickerCtrl(self.panel, wildcard= wildcard) 
        
        self.vbox_values.Add(self.path_to_hda,1,wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,5)

        self.vbox_labels.AddSpacer(10)
        self.vbox_values.AddSpacer(5)

        #button to load
        self.btn = wx.Button(self.panel,-1,"Load Path") 
        self.vbox_labels.Add(self.btn,0,wx.ALIGN_LEFT)
        self.btn.Bind(wx.EVT_BUTTON,self.OnClickedLoadPath) 

        self.hbox_main.Add(self.vbox_labels)
        self.hbox_main.AddSpacer(30)
        self.hbox_main.Add(self.vbox_values)
            
        self.panel.SetSizerAndFit(self.hbox_main)


        self.SetSize(wx.Size(1100, 700))
        self.panel.SetSize(wx.Size(450,700))

        self.Refresh()

        self.Centre() 
        self.Show() 
        self.Fit()

    def onClose(self, event):
        self.Destroy()
        #sys.exit(0)

        
    #make reference to HDA
    def initializeHDA(self, path_to_hda):
        hou.hipFile.clear()
        hou.hda.installFile(path_to_hda)
        hdas = hou.hda.definitionsInFile(path_to_hda)
        hda = hdas[0]

        global main_node
        main_node= hou.node("/obj").createNode(hda.nodeType().name())

    def readHDA(self, parm_folder):

        
        params = main_node.parmsInFolder([parm_folder])
        parm_template_group = main_node.parmTemplateGroup()

        global data
        global color_data
        global multiparms
        global names
        global y_loc
        data = {}
        color_data = {}
        multiparms = []
        names = []
        multiparm_params = {}
        y_loc = []
        color = 0

        y_loc.append(0)

        parameter_template = parm_template_group.findFolder(parm_folder)

        allParmTemplates(parameter_template)

        temp_folder = ""

        #add parameters to menu
        for param in params:
            
            name = param.name()
            label = param.description()
            value = param.eval()
            parm_template = param.parmTemplate()
            folders = param.containingFolders()
            folder = folders[len(folders)-1]

            #create headers
            if folder != temp_folder:
                font = wx.Font(15, family = wx.FONTFAMILY_MODERN, style = 0, weight = 70, 
                      underline = False, faceName ="", encoding = wx.FONTENCODING_DEFAULT)

                temp_folder = folder

                hbox1 = wx.BoxSizer(wx.HORIZONTAL)
                l1 = wx.StaticText(self.panel, -1, folder)
                l1.SetFont(font)
                hbox1.Add(l1, 1, wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,5)
                self.vbox_labels.Add(hbox1)

                hbox2 = wx.BoxSizer(wx.HORIZONTAL)
                self.vbox_values.Add(hbox2)
                self.vbox_labels.AddSpacer(8)
                self.vbox_values.AddSpacer(40)
                y_loc[0] += 40
            
            color = self.getParams(name, label, value, color, param, parm_template)
            
        i = 0
        #add multiparm handling to the bottom of the menu
        for multiparm in multiparms:
            label = multiparm.label()
            l1 = wx.StaticText(self.panel, -1, label)
            self.vbox_labels.Add(l1, 1, wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,10)

            multiparm_params[multiparm]=[]

            self.sld = wx.Slider(self.panel, wx.ID_ANY, value = 0, minValue = 0, maxValue = 10,style = wx.SL_HORIZONTAL|wx.SL_LABELS)
            slider_value.append(0)
            self.sld.Bind(wx.EVT_SLIDER, self.getOnMultiParmSliderScroll(i), self.sld)
            self.vbox_values.Add(self.sld,1,flag = wx.EXPAND, border = 20)
            self.vbox_labels.AddSpacer(10)
            self.vbox_values.AddSpacer(5)
            #vbox_labels.Add(hbox_temp)
            i+=1

        #button to export
        self.btn = wx.Button(self.panel,-1,"Export") 
        self.vbox_labels.Add(self.btn,0,wx.ALIGN_LEFT)
        self.btn.Bind(wx.EVT_BUTTON, self.OnClickedExport)
        self.vbox_labels.AddSpacer(10)
        self.vbox_values.AddSpacer(25)
        
        self.panel.SetSizerAndFit(self.hbox_main)


        self.SetSize(wx.Size(1100, 700))
        self.panel.SetSize(wx.Size(450,700))
        self.glpanel = GLPanel(self.main_splitter)
        self.main_splitter.SplitVertically(self.panel, self.glpanel)
       
        self.Refresh()

        self.Centre() 
        self.Show() 
        self.Fit()

    def getParams(self, name, label, value, color, param, parm_template):
        #ignore duplicate parms (esp for adding multiparms)
        if name in names:
            return
        #add sting parm
        if isinstance(value, str):
            l1 = wx.StaticText(self.panel, -1, label)
            self.vbox_labels.Add(l1, 1, wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,5)

            self.param = wx.TextCtrl(self.panel)
            self.param.SetValue(value)
            self.vbox_values.Add(self.param,0,wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,0)
            self.vbox_labels.AddSpacer(8)
            self.vbox_values.AddSpacer(10)

            y_loc[0] += 30
            
        
            data[param] = self.param.GetValue
                
        elif isinstance(value, int):
            #add switch/toggle parm
            if parm_template.type() == hou.parmTemplateType.Toggle: 
                self.cb1 = wx.CheckBox(self.panel, label=label, pos=(50, 50))
                self.vbox_labels.Add(self.cb1, 1, flag = wx.EXPAND, border = 5)
                hbox2 = wx.BoxSizer(wx.HORIZONTAL)
                self.vbox_values.Add(hbox2)
                
                self.vbox_labels.AddSpacer(8)
                self.vbox_values.AddSpacer(45)
                
                if value == 1:
                    self.cb1.SetValue(1)
                else:
                    self.cb1.SetValue(0)

                y_loc[0] += 35

                data[param] = self.cb1.GetValue

            #add menu parm
            elif parm_template.type() == hou.parmTemplateType.Menu:

                l1 = wx.StaticText(self.panel, -1, label) 
                self.vbox_labels.Add(l1, 1, wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,5)
                
                menu_items = parm_template.menuLabels()

                self.choice = wx.Choice(self.panel,choices = menu_items)
                self.choice.SetSelection(0)
                self.vbox_values.Add(self.choice,1,wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,5)
                
                self.vbox_labels.AddSpacer(10)
                self.vbox_values.AddSpacer(10)
                
                y_loc[0] += 35
                
                data[param] = self.choice.GetSelection
            #add integer parm    
            else:
                min_v = parm_template.minValue()
                max_v = parm_template.maxValue()

                l1 = wx.StaticText(self.panel, -1, label) 
                self.vbox_labels.Add(l1, 1, wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,5)

                self.sld = wx.Slider(self.panel, value = value, minValue = min_v, maxValue = max_v,style = wx.SL_HORIZONTAL|wx.SL_LABELS)
                self.vbox_values.Add(self.sld,1,flag = wx.EXPAND, border = 5)

                self.vbox_labels.AddSpacer(15)
                self.vbox_values.AddSpacer(5)

                y_loc[0] += 35

                data[param] = self.sld.GetValue
                    
        elif isinstance(value, float):
        #add vector/color parm
            min_v = parm_template.minValue()
            max_v = parm_template.maxValue()
            if parm_template.numComponents() == 3:

                if color == 0:
                    
                    label = label + " R"
                    color = color + 1
                    color_data[name[0:(len(name)-1)]] = y_loc[0]
                        
                elif color == 1:

                    label = label + " G"
                    color = color + 1      
                        
                elif color == 2:

                    label = label + " B"
                    color = 0


                l1 = wx.StaticText(self.panel, -1, label) 
                self.vbox_labels.Add(l1, 1, wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,5)

                self.floatspin = FS.FloatSpin(self.panel, -1, pos=(50, 50), min_val=min_v, max_val=max_v, increment=0.01, value=value, agwStyle=FS.FS_LEFT)
                self.floatspin.SetFormat("%f")
                self.floatspin.SetDigits(2)
                self.floatspin.Bind(FS.EVT_FLOATSPIN, self.OnFloatSpinColor)
                self.vbox_values.Add(self.floatspin,1,flag = wx.EXPAND, border = 5)

                self.vbox_labels.AddSpacer(12)
                self.vbox_values.AddSpacer(7)
                
                y_loc[0] += 47
                color_data[name] = self.floatspin.GetValue
                data[param] = self.floatspin.GetValue
                    
                self.panel.Bind(wx.EVT_PAINT, self.getOnPaint)
                self.Refresh()
                names.append(name)
                
                return color
            #add float parm
            else:

                l1 = wx.StaticText(self.panel, -1, label)
                self.vbox_labels.Add(l1, 1, wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,5)

                self.floatspin = FS.FloatSpin(self.panel, -1, pos=(50, 50), min_val=min_v, max_val=max_v, increment=0.01, value=value, agwStyle=FS.FS_LEFT)
                self.floatspin.SetFormat("%f")
                if min_v < .01:
                    self.floatspin.SetDigits(3)
                else:
                    self.floatspin.SetDigits(2)
                self.vbox_values.Add(self.floatspin,1,flag = wx.EXPAND, border = 5)

                self.vbox_labels.AddSpacer(10)
                self.vbox_values.AddSpacer(7)
                
                y_loc[0] += 47
                
                data[param] = self.floatspin.GetValue

        names.append(name)
        return 0
        
    def getOnMultiParmSliderScroll(self, index):
        def OnMultiParmSliderScroll(event):
            temp_sld = event.GetEventObject()
            
            if slider_value[index] == temp_sld.GetValue():
                print("enters")
            elif slider_value[index] > temp_sld.GetValue() and slider_value[index] != 0 and slider_value[index] > self.sld.GetValue():
                
                multi = main_node.parm(multiparms[index].name())

                params = multi.multiParmInstances()
                
                #remove the parameters based on the number of parameter templates in the multiparm
                i = (multi.multiParmInstancesCount()-1)
                print("i: " +str(i))

                
                for parm_temp in multiparms[index].parmTemplates():
                    param = params[i]
                    #for item in values
                    self.vbox_values.Hide(self.vbox_values.GetItemCount()-1)
                    self.vbox_values.Remove(self.vbox_values.GetItemCount()-1)
                    #for spacer added after item
                    self.vbox_values.Hide(self.vbox_values.GetItemCount()-1)
                    self.vbox_values.Remove(self.vbox_values.GetItemCount()-1)
                    #for item in labels
                    self.vbox_labels.Hide(self.vbox_labels.GetItemCount()-1)
                    self.vbox_labels.Remove(self.vbox_labels.GetItemCount()-1)
                    #for spacer added after item
                    self.vbox_labels.Hide(self.vbox_labels.GetItemCount()-1)
                    self.vbox_labels.Remove(self.vbox_labels.GetItemCount()-1)
                    
                    
                    names.pop()
                    data.pop(param)

                    i -= 1

                #remove multiparm number label
                self.vbox_values.Hide(self.vbox_values.GetItemCount()-1)
                self.vbox_values.Remove(self.vbox_values.GetItemCount()-1)
                self.vbox_labels.Hide(self.vbox_labels.GetItemCount()-1)
                self.vbox_labels.Remove(self.vbox_labels.GetItemCount()-1)
                #And spacer
                self.vbox_values.Hide(self.vbox_values.GetItemCount()-1)
                self.vbox_values.Remove(self.vbox_values.GetItemCount()-1)
                self.vbox_labels.Hide(self.vbox_labels.GetItemCount()-1)
                self.vbox_labels.Remove(self.vbox_labels.GetItemCount()-1)

                multi.removeMultiParmInstance(slider_value[index]-1)

                self.panel.SetSizer(self.hbox_main)
                self.panel.FitInside()
                self.Refresh()
                
            else:
                #add header
                font = wx.Font(15, family = wx.FONTFAMILY_MODERN, style = 0, weight = 70, 
                      underline = False, faceName ="", encoding = wx.FONTENCODING_DEFAULT)
                l1 = wx.StaticText(self.panel, -1, "Multiparm #" + str(slider_value[index]+1))
                l1.SetFont(font)
                self.vbox_labels.Add(l1, 1, wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,5)
                

                l2 = wx.StaticText(self.panel, -1, "")
                self.vbox_values.Add(l2, 1, wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,5)
                self.vbox_labels.AddSpacer(8)
                self.vbox_values.AddSpacer(10)

                
                multi = main_node.parm(multiparms[index].name())
                
                multi.insertMultiParmInstance(slider_value[index])
                params = multi.multiParmInstances()

                color = 0
                #add multiparm parameters to menu
                for param in params:
                    name = param.name()
                    label = param.description()
                    value = param.eval()
                    parm_template = param.parmTemplate()

                    
            
                    color = self.getParams(name, label, value, color, param, parm_template)
                self.panel.SetSizer(self.hbox_main)
                self.panel.FitInside()
                self.Refresh()
                    
            slider_value[index] = temp_sld.GetValue()
            print("new slider value is: "+ str(slider_value[index]))

        return OnMultiParmSliderScroll
        
    def OnClickedLoadPath(self, event):
        path_to_HDA_s = self.path_to_hda.GetPath()
        self.initializeHDA(path_to_HDA_s)
        params = main_node.parms()
        list_of_folders = []
        for param in params:
            folders = param.containingFolders()
            for folder in folders:
                if folder in list_of_folders:
                    pass
                else:
                    list_of_folders.append(folder)

        self.vbox_values.AddSpacer(25)
        self.vbox_labels.AddSpacer(5)
        
        l1 = wx.StaticText(self.panel, -1, "Folder") 
        self.vbox_labels.Add(l1, 1, wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,5)

        self.folder_menu = wx.Choice(self.panel,choices = list_of_folders)
        self.folder_menu.SetSelection(0)
        self.vbox_values.Add(self.folder_menu,1,wx.EXPAND|wx.ALIGN_LEFT|wx.ALL,5)
        
        self.vbox_labels.AddSpacer(10)
        self.vbox_values.AddSpacer(5)

        #button to load folder
        self.folderbtn = wx.Button(self.panel,-1,"Load Folder") 
        self.vbox_labels.Add(self.folderbtn,0,wx.ALIGN_LEFT)
        self.folderbtn.Bind(wx.EVT_BUTTON,self.OnClickedLoadFolder)

        self.vbox_labels.AddSpacer(10)
        self.vbox_values.AddSpacer(40)
            
        self.panel.SetSizerAndFit(self.hbox_main)

        self.Refresh()

        self.Centre() 
        self.Show() 
        self.Fit()
        

    def OnClickedLoadFolder(self, event):
        folder_int = self.folder_menu.GetSelection()
        folder_s = self.folder_menu.GetString(folder_int)
        self.readHDA(folder_s)
        

    def OnFloatSpinColor(self, event):
        self.Refresh()

    def getOnPaint(self, event):
        dc = wx.PaintDC(self.panel)
        wx.ScrolledWindow.PrepareDC(self.panel, dc)
        i = 0
        while i < len(color_data):
            sub_name = list(color_data.keys())[i][0:(len(list(color_data.keys())[i]))]
            color_values = wx.Colour((color_data[sub_name+'r']()*255), (color_data[sub_name+'g']()*255), color_data[sub_name+'b']()*255)
            dc.SetBrush(wx.Brush(color_values))
            dc.DrawRectangle(400,((color_data[sub_name])+175), 100,40)
            i += 4
        del dc

    def OnClickedExport(self, event):
        folder_int = self.folder_menu.GetSelection()
        folder_s = self.folder_menu.GetString(folder_int)
        self.export(folder_s)

    def export(self, parm_folder):
        params = main_node.parmsInFolder([parm_folder])
        
        for param in params:
            if data.get(param) is not None:
                res = data[param]()
                param.set(res)

        for multiparm in multiparms:
            multi = main_node.parm(multiparm.name())
            params = multi.multiParmInstances()
            for param in params:
                if data.get(param) is not None:
                    res = data[param]()
                    param.set(res)
        
        main_node.parm('execute').pressButton()

                              
app = wx.App() 
frm = Mywin(None,  title='HDA Editor')

app.MainLoop()
del app
