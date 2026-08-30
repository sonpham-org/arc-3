"""q015 Reciprocal Hands -- helpers reciprocate a short history of assistance or obstruction."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HALL,HELP,BLOCK,REPLY,DONE,BAD=7,1,14,8,9,10,13
LEVELS=[
 {"name":"Return Help","hist":[[1]],"rule":0}, {"name":"Remember Last","hist":[[1,0],[0,1]],"rule":0},
 {"name":"Majority Memory","hist":[[1,1,0],[0,1,0],[1,0,1]],"rule":1}, {"name":"Two Helpers","hist":[[0,1,1],[1,0,0],[1,1,0],[0,0,1]],"rule":1},
 {"name":"Recent Reciprocity","hist":[[1,0,1],[0,1,0],[1,1,1],[0,0,1],[1,0,0]],"rule":0}, {"name":"Reciprocal Hands","hist":[[1,0,1],[0,1,0],[1,1,0],[0,0,1],[1,1,1],[0,0,0]],"rule":1}]
def reply(h,rule):return (h[-1] if rule==0 else int(sum(h)*2>=len(h)))+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=HALL
  for i,h in enumerate(g.hist):x=7+i*8
  
  for i,h in enumerate(g.hist):
   x=7+i*8
   for j,v in enumerate(h):f[15+j*6:20+j*6,x:x+6]=HELP if v else BLOCK
   f[40:47,x:x+6]=DONE if i<g.progress else REPLY
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q015(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.hist=[];self.rule=self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q015",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.hist=[list(x) for x in s["hist"]];self.rule=s["rule"];self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a!=reply(self.hist[self.progress],self.rule):self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.hist):self.next_level()
  self.complete_action()
