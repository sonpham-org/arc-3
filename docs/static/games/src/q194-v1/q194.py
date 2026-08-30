"""q194 Interrupt Window -- let routines run and interrupt only at useful state windows."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,PHASE,WINDOW,CAPTURE,DONE,BAD=15,0,10,14,9,6,8
LEVELS=[
 {"name":"First Window","period":3,"windows":[1]}, {"name":"Run Then Stop","period":4,"windows":[2,0]},
 {"name":"Two Interrupts","period":5,"windows":[3,1]}, {"name":"Sparse Window","period":6,"windows":[4,2,5]},
 {"name":"Routine State","period":7,"windows":[5,1,6]}, {"name":"Interrupt Window","period":8,"windows":[6,2,7,3]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=STAGE
  for i in range(g.period):x=7+i*6;f[20:29,x:x+5]=WINDOW if i==g.phase else PHASE
  for i,w in enumerate(g.windows):x=9+i*11;f[39:46,x:x+8]=DONE if i<g.progress else CAPTURE;f[41:44,x:x+w%6+2]=WINDOW
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q194(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.period=self.phase=self.progress=0;self.windows=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q194",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.period=s["period"];self.windows=list(s["windows"]);self.phase=self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==5:self.phase=(self.phase+1)%self.period
  elif a==6:
   if self.phase==self.windows[self.progress]:
    self.progress+=1
    if self.progress==len(self.windows):self.next_level()
    else:self.phase=(self.phase+1)%self.period
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
