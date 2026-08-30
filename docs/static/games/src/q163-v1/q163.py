"""q163 Evidence Weight -- allocate differently reliable evidence before commitment."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BENCH,EVIDENCE,LEFT,RIGHT,CURSOR,DONE,BAD=12,1,10,9,15,11,14,8
LEVELS=[
 {"name":"One Piece","weights":[1],"assign":[0]}, {"name":"Opposed Evidence","weights":[1,2],"assign":[0,1]},
 {"name":"Reliability","weights":[1,3,2],"assign":[1,0,1]}, {"name":"Weighted Case","weights":[2,1,4,3],"assign":[0,1,1,0]},
 {"name":"Conflicting Pieces","weights":[1,4,2,3,2],"assign":[1,0,1,0,0]}, {"name":"Evidence Weight","weights":[2,5,1,4,3,2],"assign":[0,1,0,1,1,0]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=BENCH
  for i,w in enumerate(g.weights):
   x=8+i*8;c=DONE if i in g.placed else EVIDENCE;f[20-w:22,x:x+6]=c;f[14:17,x:x+6]=CURSOR if i==g.cursor else BENCH
   if i in g.placed:f[38+g.placed[i]*9:44+g.placed[i]*9,x:x+6]=LEFT if g.placed[i]==0 else RIGHT
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q163(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.weights=self.assign=[];self.cursor=0;self.placed={};self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q163",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.weights=list(s["weights"]);self.assign=list(s["assign"]);self.cursor=0;self.placed={};self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.weights)
  elif a==4:self.cursor=(self.cursor+1)%len(self.weights)
  elif a in (1,2):self.placed[self.cursor]=a-1
  elif a==6:
   if len(self.placed)==len(self.weights) and all(self.placed[i]==v for i,v in enumerate(self.assign)):self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
