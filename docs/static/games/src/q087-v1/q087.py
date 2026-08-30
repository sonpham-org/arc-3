"""q087 Body Exchange -- identities retain destinations while capabilities swap bodies."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TRACK,IDA,IDB,BODY1,BODY2,DEST,CURSOR,BAD=4,7,9,12,10,6,14,11,8
LEVELS=[
 {"name":"Borrowed Step","start":[0,8],"dest":[2,5],"steps":[1,2]},
 {"name":"Identity Destination","start":[1,7],"dest":[6,2],"steps":[1,2]},
 {"name":"Swap Midway","start":[0,8],"dest":[7,1],"steps":[1,3]},
 {"name":"Asymmetric Bodies","start":[2,6],"dest":[8,1],"steps":[2,3]},
 {"name":"Two Obligations","start":[0,7],"dest":[8,2],"steps":[1,3]},
 {"name":"Body Exchange","start":[1,8],"dest":[7,0],"steps":[2,3]}]
LIMIT=8
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=TRACK
  for i in range(9):x=8+i*6;f[29:34,x:x+4]=TRACK
  for identity,(p,d) in enumerate(zip(g.pos,g.dest)):
   x=8+p*6;color=IDA if identity==0 else IDB;body=BODY1 if g.cap[identity]==0 else BODY2;f[20+identity*18:29+identity*18,x:x+5]=body;f[22+identity*18:27+identity*18,x+1:x+4]=color;dx=8+d*6;f[14+identity*18:18+identity*18,dx:dx+5]=DEST
  f[4:7,8+g.selected*25:25+g.selected*25]=CURSOR
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q087(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pos=self.dest=[];self.steps=[];self.cap=[0,1];self.selected=0;self.budget=32;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q087",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.pos=list(s["start"]);self.dest=list(s["dest"]);self.steps=list(s["steps"]);self.cap=[0,1];self.selected=0;self.budget=32;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget-=1
  if a in (1,2):
   delta=self.steps[self.cap[self.selected]]*(-1 if a==1 else 1);n=self.pos[self.selected]+delta
   if 0<=n<=LIMIT:self.pos[self.selected]=n
  elif a==3:self.selected=0
  elif a==4:self.selected=1
  elif a==5:self.cap=self.cap[::-1]
  elif a==6:
   if self.pos==self.dest:self.next_level()
   else:self.failed=True;self.lose()
  if self.budget<=0:self.failed=True;self.lose()
  self.complete_action()
