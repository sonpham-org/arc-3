"""q614 Tessera Grammar -- transformed command chunks require a state-defined interruption."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MOSAIC,TESSERA,SEAM,GROUP,RELATION,WINDOW,BAD=3,13,9,12,14,10,6,8
MACRO=[1,2,3]
LEVELS=[
 {"name":"Grouped Chunk","target":[1,2,3,4],"shift":0,"window":3},{"name":"Relay Transform","target":[2,3,4,1,2],"shift":1,"window":2},
 {"name":"Interrupt the Macro","target":[3,4,1,2,3,4],"shift":2,"window":4},{"name":"Topology Seam","target":[4,1,2,3,1,4],"shift":3,"window":3},
 {"name":"Composed Grammar","target":[1,2,3,4,2,1,2,3],"shift":0,"window":6},{"name":"Tessera Grammar","target":[2,3,4,1,3,2,3,4,1],"shift":1,"window":7}]
def enc(a,s):return((a-1+s)%4)+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=MOSAIC
  for i in range(len(g.target)):x=7+i*6;f[20:32,x:x+4]=TESSERA;f[36:41,x:x+4]=RELATION if i<len(g.result) else GROUP
  f[45:50,7+g.window*6:11+g.window*6]=WINDOW;f[3:6,8:8+g.shift*10]=SEAM
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q614(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=self.result=[];self.shift=self.window=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q614",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.target=list(s["target"]);self.shift=s["shift"];self.window=s["window"];self.result=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3,4):self.result.append(enc(z,self.shift))
  elif z==5:
   if len(self.result)<self.window<len(self.result)+3:self.failed=True;self.lose()
   else:self.result += [enc(a,self.shift) for a in MACRO]
  elif z==6:
   if self.result==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
