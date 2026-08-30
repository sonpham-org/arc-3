"""q005 Lantern Census -- hidden populations grow while illuminated ones merge."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,YARD,PEN,CREATURE,LANTERN,TARGET,CURSOR,BAD=6,1,3,14,11,9,12,8
LEVELS=[
 {"name":"One Lantern","start":[1,3],"target":[2,2],"ticks":1}, {"name":"Hide and Merge","start":[2,4],"target":[4,2],"ticks":2},
 {"name":"Three Pens","start":[1,3,4],"target":[3,3,2],"ticks":2}, {"name":"Alternating Light","start":[4,1,2],"target":[2,3,4],"ticks":2},
 {"name":"Census Plan","start":[1,2,4,3],"target":[3,4,2,3],"ticks":2}, {"name":"Lantern Census","start":[4,1,3,2],"target":[2,3,3,4],"ticks":2}]
def evolve(vals,lit):return tuple(max(1,v-1) if i in lit else min(5,v+1) for i,v in enumerate(vals))
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=YARD;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):
   x=8+i*(49//n);f[17:47,x:x+10]=PEN
   for j in range(v):f[42-j*5:46-j*5,x+2:x+8]=CREATURE
   f[12:15,x:x+t*2]=TARGET
   if i in g.lit:f[48:53,x:x+10]=LANTERN
  f[4:7,8+g.cursor*(49//n):18+g.cursor*(49//n)]=CURSOR
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q005(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=();self.lit=set();self.cursor=self.ticks=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q005",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.values=tuple(s["start"]);self.target=tuple(s["target"]);self.ticks=s["ticks"];self.cursor=0;self.lit=set();self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.values)
  elif a==4:self.cursor=(self.cursor+1)%len(self.values)
  elif a==5:self.lit.symmetric_difference_update({self.cursor})
  elif a==6 and self.ticks:self.values=evolve(self.values,self.lit);self.ticks-=1
  elif a==1:
   if self.values==self.target and self.ticks==0:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
