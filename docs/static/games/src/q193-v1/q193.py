"""q193 Routine Builder -- package a repeated temporal motif without hiding its branch."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,TARGET,RAW,MACRO,DONE,BAD=15,1,10,9,12,14,8
LEVELS=[
 {"name":"First Routine","motif":[1],"repeats":2,"suffix":[]},
 {"name":"Two-Step Macro","motif":[1,4],"repeats":2,"suffix":[]},
 {"name":"Repeat Then Branch","motif":[2,3],"repeats":2,"suffix":[4]},
 {"name":"Three Repetitions","motif":[1,4,2],"repeats":3,"suffix":[3]},
 {"name":"Hidden Branch","motif":[3,1,4],"repeats":3,"suffix":[2,2]},
 {"name":"Routine Builder","motif":[1,4,2,3],"repeats":4,"suffix":[4,1,2]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=STAGE
  for i,a in enumerate(g.target[:18]):x=6+i*3;f[15+a*3:18+a*3,x:x+2]=DONE if i<len(g.output) else TARGET
  for i,a in enumerate(g.buffer):f[36:41,8+i*7:13+i*7]=RAW
  if g.macro:f[46:52,8:8+len(g.macro)*7]=MACRO
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q193(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=[];self.output=[];self.buffer=[];self.macro=[];self.recording=True;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q193",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.target=list(s["motif"])*s["repeats"]+list(s["suffix"]);self.output=[];self.buffer=[];self.macro=[];self.recording=True;self.failed=False
 def emit(self,seq):
  if self.output+list(seq)!=self.target[:len(self.output)+len(seq)]:self.failed=True;self.lose();return
  self.output.extend(seq)
  if self.output==self.target:self.next_level()
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if 1<=a<=4:
   if self.recording:self.buffer.append(a)
   self.emit([a])
  elif a==5 and self.recording and self.buffer:self.macro=list(self.buffer);self.recording=False
  elif a==6 and self.macro:self.emit(self.macro)
  else:self.failed=True;self.lose()
  self.complete_action()
