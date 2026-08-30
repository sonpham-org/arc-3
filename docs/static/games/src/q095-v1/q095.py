"""q095 Closure Graph -- small completed cycles unlock nested larger cycles."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BOARD,NODE,EDGE,CLOSED,TARGET,CURSOR,BAD=15,12,3,10,14,6,11,8
LEVELS=[
 {"name":"First Cycle","cycles":[[0,1]],"nodes":2}, {"name":"Nested Pair","cycles":[[0,1],[0,1,2]],"nodes":3},
 {"name":"Two Small Cycles","cycles":[[0,1],[2,3],[0,1,2,3]],"nodes":4}, {"name":"Shared Closure","cycles":[[0,1],[1,2],[0,1,2,3]],"nodes":4},
 {"name":"Closure Ladder","cycles":[[0,1],[2,3],[0,1,2,3],[0,1,2,3,4]],"nodes":5}, {"name":"Closure Graph","cycles":[[0,1],[2,3],[3,4],[0,1,2,3,4],[0,1,2,3,4,5]],"nodes":6}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=BOARD
  for i in range(g.nodes):x=8+i*9;f[27:36,x:x+7]=CLOSED if i in g.done else NODE;f[39:43,x:x+7]=CURSOR if i==g.cursor else BOARD
  for j,c in enumerate(g.cycles):f[12+j*5:15+j*5,7:7+len(c)*9]=CLOSED if all(i in g.done for i in c) else EDGE
  f[3:6,7:7+g.nodes*9]=TARGET
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q095(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.cycles=[];self.nodes=self.cursor=0;self.done=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q095",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.cycles=[list(x) for x in s["cycles"]];self.nodes=s["nodes"];self.cursor=0;self.done=set();self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%self.nodes
  elif a==4:self.cursor=(self.cursor+1)%self.nodes
  elif a==5:self.done.add(self.cursor)
  elif a==6:
   if all(all(i in self.done for i in c) for c in self.cycles):self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
