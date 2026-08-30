"""q075 Betrayal Gate -- a visible wear cue flips a learned activation rule."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HALL,GATE,WEAR,CUE,DONE,BAD=11,0,10,8,9,14,13
LEVELS=[
 {"name":"Wear Flip","cues":[0,1],"wear":1}, {"name":"Complement Rule","cues":[1,0,1],"wear":1},
 {"name":"Late Betrayal","cues":[0,1,1,0],"wear":2}, {"name":"Visible Expiry","cues":[1,1,0,1,0],"wear":3},
 {"name":"Gate Memory","cues":[0,1,0,1,1,0],"wear":3}, {"name":"Betrayal Gate","cues":[1,0,1,1,0,0,1],"wear":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=HALL
  for i,c in enumerate(g.cues):x=7+i*8;f[18:29,x:x+6]=GATE;f[12:16,x:x+6]=WEAR if i>=g.wear else CUE;f[38:45,x:x+6]=DONE if i<g.progress else CUE+c
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q075(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.cues=[];self.wear=self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q075",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.cues=list(s["cues"]);self.wear=s["wear"];self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  expected=self.cues[self.progress] if self.progress<self.wear else 1-self.cues[self.progress];expected+=1
  if a!=expected:self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.cues):self.next_level()
  self.complete_action()
