"""q029 Fuse Map -- irreversible cuts reveal flow while preserving the needed circuit."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BOARD,FUSE,FLOW,CUT,GOAL,CURSOR,BAD=14,1,3,9,8,12,11,6
LEVELS=[
 {"name":"Preserve One Branch","count":3,"needed":[0]}, {"name":"Downstream Reveal","count":4,"needed":[0,2]},
 {"name":"Shared Supply","count":5,"needed":[0,3]}, {"name":"Diagnostic Cut","count":6,"needed":[0,2,5]},
 {"name":"One Live Circuit","count":7,"needed":[0,1,4]}, {"name":"Fuse Map","count":8,"needed":[0,2,5,7]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=BOARD
  for i in range(g.count):
   x=7+i*6;f[20:40,x:x+5]=CUT if i in g.cut else FUSE;f[15:18,x:x+5]=CURSOR if i==g.cursor else BOARD;f[43:47,x:x+5]=FLOW if i in g.revealed and i in g.needed else CUT if i in g.revealed else BOARD
  f[49:53,8:56]=GOAL
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q029(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.count=self.cursor=0;self.needed=self.cut=self.revealed=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q029",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.count=s["count"];self.needed=set(s["needed"]);self.cursor=0;self.cut=set();self.revealed=set();self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==3:self.cursor=(self.cursor-1)%self.count
  elif z==4:self.cursor=(self.cursor+1)%self.count
  elif z==5:
   if self.cursor in self.needed:self.failed=True;self.lose()
   else:self.cut.add(self.cursor);self.revealed.update(range(self.cursor,self.count))
  elif z==6:
   if self.cut==set(range(self.count))-self.needed:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
