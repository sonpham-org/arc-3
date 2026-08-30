"""q010 Shared Blindspot -- two observers create Boolean visibility control regions."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,PIECE,OBSA,OBSB,TARGET,CURSOR,BAD=9,1,10,12,14,6,11,8
LEVELS=[
 {"name":"Either Observer","mod":4,"start":[0,0],"triggers":[1,1],"plan":[1,5,4,2,5]},
 {"name":"Both Watch","mod":5,"start":[1,0,2],"triggers":[2,1,0],"plan":[1,2,5,4,1,5]},
 {"name":"Neither Moves","mod":5,"start":[0,2,1],"triggers":[0,1,2],"plan":[5,4,1,5,4,2,5]},
 {"name":"Boolean Regions","mod":6,"start":[2,0,3,1],"triggers":[1,2,0,1],"plan":[1,5,4,2,1,5,4,4,2,5]},
 {"name":"Joint Attention","mod":6,"start":[0,1,4,2],"triggers":[2,0,1,2],"plan":[1,2,5,4,1,5,4,2,2,5]},
 {"name":"Shared Blindspot","mod":7,"start":[1,5,0,3,2],"triggers":[0,1,2,1,0],"plan":[5,4,1,5,4,2,1,5,4,4,2,5]}]
def derive(level):
 vals=list(level["start"]);masks=[0]*len(vals);cur=0
 for z in level["plan"]:
  if z==1:masks[cur]^=1
  elif z==2:masks[cur]^=2
  elif z==3:cur=(cur-1)%len(vals)
  elif z==4:cur=(cur+1)%len(vals)
  elif z==5:vals=[(v+1)%level["mod"] if masks[i].bit_count()==level["triggers"][i] else v for i,v in enumerate(vals)]
 return vals
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=FIELD;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):
   x=7+i*(50//n);f[24:39,x:x+8]=PIECE;f[34-v*2:37,x+2:x+6]=TARGET;f[15:19,x:x+8]=OBSA if g.masks[i]&1 else FIELD;f[19:23,x:x+8]=OBSB if g.masks[i]&2 else FIELD;f[43:47,x:x+t+2]=TARGET;f[50:53,x:x+8]=CURSOR if i==g.cursor else FIELD
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q010(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=self.triggers=[];self.masks=[];self.mod=self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q010",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=list(s["start"]);self.target=derive(s);self.triggers=list(s["triggers"]);self.masks=[0]*len(self.values);self.mod=s["mod"];self.cursor=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.masks[self.cursor]^=1
  elif z==2:self.masks[self.cursor]^=2
  elif z==3:self.cursor=(self.cursor-1)%len(self.values)
  elif z==4:self.cursor=(self.cursor+1)%len(self.values)
  elif z==5:self.values=[(v+1)%self.mod if self.masks[i].bit_count()==self.triggers[i] else v for i,v in enumerate(self.values)]
  elif z==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
