"""q086 Doppel Memory -- distinguish an original from a duplicate by learned permissions."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HALL,BODY,TRAIL,PERMIT,TARGET,CURSOR,BAD=1,10,9,3,14,6,12,8
LEVELS=[
 {"name":"Permission Test","count":2,"original":0,"tests":[0]}, {"name":"Copied Trail","count":3,"original":2,"tests":[1,2]},
 {"name":"Doppel Pair","count":3,"original":1,"tests":[0,2,1]}, {"name":"Behavioral Memory","count":4,"original":3,"tests":[2,0,3]},
 {"name":"Identical Histories","count":5,"original":2,"tests":[1,4,0,2]}, {"name":"Doppel Memory","count":6,"original":4,"tests":[3,1,5,0,4]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=HALL
  for i in range(g.count):x=8+i*8;f[22:34,x:x+6]=BODY;f[16:19,x:x+6]=TRAIL;f[38:42,x:x+6]=PERMIT if i in g.tested and i==g.original else TRAIL if i in g.tested else HALL;f[44:48,x:x+6]=CURSOR if i==g.cursor else HALL
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q086(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.count=self.original=self.cursor=self.test_cursor=0;self.tests=[];self.tested=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q086",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.count=s["count"];self.original=s["original"];self.tests=list(s["tests"]);self.cursor=self.test_cursor=0;self.tested=set();self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%self.count
  elif a==4:self.cursor=(self.cursor+1)%self.count
  elif a==5:self.tested.add(self.tests[self.test_cursor]);self.test_cursor=min(len(self.tests)-1,self.test_cursor+1)
  elif a==6:
   if self.cursor==self.original and self.original in self.tested:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
