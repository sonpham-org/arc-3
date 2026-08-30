"""q006 Shadow Cargo -- transfer cargo only between simultaneously unwatched pockets."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HOLD,POCKET,CARGO,WATCH,TARGET,CURSOR,BAD=9,1,3,14,11,10,12,8
LEVELS=[
 {"name":"Dark Transfer","start":[2,0],"target":[1,1],"ops":[(0,1)]}, {"name":"Lock Storage","start":[3,0,0],"target":[1,1,1],"ops":[(0,1),(0,2)]},
 {"name":"Paired Shadows","start":[2,1,0],"target":[1,1,1],"ops":[(0,2),(1,2),(0,1)]}, {"name":"Watched Buffer","start":[4,0,0],"target":[1,2,1],"ops":[(0,1),(1,2),(0,2)]},
 {"name":"Cargo Ring","start":[3,1,0,0],"target":[1,1,1,1],"ops":[(0,1),(1,2),(2,3),(0,3)]}, {"name":"Shadow Cargo","start":[4,1,0,0],"target":[1,1,2,1],"ops":[(0,1),(1,2),(2,3),(0,3),(0,2)]}]
def move(vals,op,watched):
 a,b=op;o=list(vals)
 if a not in watched and b not in watched and o[a]:o[a]-=1;o[b]+=1
 return tuple(o)
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=HOLD;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):
   x=9+i*(47//n);f[19:43,x:x+9]=POCKET
   for j in range(v):f[39-j*5:43-j*5,x+2:x+7]=CARGO
   f[13:16,x:x+t*3]=TARGET
   if i in g.watched:f[45:50,x:x+9]=WATCH
  for i in range(len(g.ops)):f[3:6,6+i*8:12+i*8]=CURSOR if i==g.cursor else POCKET
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q006(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=();self.ops=[];self.cursor=0;self.watched=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q006",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.values=tuple(s["start"]);self.target=tuple(s["target"]);self.ops=list(map(tuple,s["ops"]));self.cursor=0;self.watched=set();self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.ops)
  elif a==4:self.cursor=(self.cursor+1)%len(self.ops)
  elif a==1:self.watched.symmetric_difference_update({self.ops[self.cursor][0]})
  elif a==2:self.watched.symmetric_difference_update({self.ops[self.cursor][1]})
  elif a==5:self.values=move(self.values,self.ops[self.cursor],self.watched)
  elif a==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
