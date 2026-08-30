"""q356 Palimpsest Rig -- construct one geometry that survives two functional tests."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,SLOT,REDIRECT,JOIN,SUPPORT,PASS,BAD=15,4,12,9,10,14,6,8
LEVELS=[
 {"name":"Redirect Component","target":[1,2,1],"failed":[1,3,1]},
 {"name":"Visible Counterexample","target":[2,1,3],"failed":[2,2,3]},
 {"name":"Join and Support","target":[3,1,2,1],"failed":[3,1,3,1]},
 {"name":"Rotated Function","target":[1,3,2,2],"failed":[1,3,1,2]},
 {"name":"Reusable Device","target":[2,3,1,2,1],"failed":[2,3,1,3,1]},
 {"name":"Palimpsest Rig","target":[3,2,1,3,2],"failed":[3,2,2,3,2]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=ARCHIVE;n=len(g.slots)
  for i,v in enumerate(g.slots):x=8+i*(48//n);f[18:34,x:x+8]=SLOT if v==0 else (REDIRECT,JOIN,SUPPORT)[v-1];f[38:42,x:x+8]=(REDIRECT,JOIN,SUPPORT)[g.failed_example[i]-1]
  f[46:50,8:8+g.cursor*(48//n)]=PASS;f[3:6,8:8+g.passed*14]=PASS
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q356(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=self.failed_example=self.slots=[];self.cursor=self.passed=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q356",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.target=list(s["target"]);self.failed_example=list(s["failed"]);self.slots=[0]*len(self.target);self.cursor=self.passed=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3) and self.passed==0:self.slots[self.cursor]=z
  elif z==4 and self.passed==0:self.cursor=(self.cursor+1)%len(self.slots)
  elif z==5:
   expected=self.target[self.passed:]+self.target[:self.passed]
   if self.slots!=expected:self.failed=True;self.lose()
   else:self.passed+=1;self.slots=self.slots[1:]+self.slots[:1]
  elif z==6:
   if self.passed==2:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
