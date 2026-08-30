"""q485 Waystation Dependency -- solve a DAG while avoiding repeated-policy counters."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,DESERT,WALKER,DUNE,DONE,POLICY,CURSOR,BAD=4,12,13,10,15,14,6,8
LEVELS=[{"name":n,"deps":d,"order":o,"policies":p,"rewire":r} for n,d,o,p,r in [("Supply Request",[[],[0],[0]],[0,1,2],[1,2,1],1),("Shared Walker",[[],[0],[0],[1,2]],[0,2,1,3],[1,2,1,2],2),("Counter State",[[],[0],[1],[0],[2,3]],[0,1,2,3,4],[1,2,1,2,1],2),("Dune Corridors",[[],[],[0,1],[1],[2,3]],[1,0,3,2,4],[1,2,1,2,1],3),("Reusable Supply",[[],[0],[0],[1,2],[2],[3,4]],[0,2,1,4,3,5],[1,2,1,2,1,2],3),("Waystation Dependency",[[],[],[0],[0,1],[2,3],[1,4]],[1,0,2,3,4,5],[1,2,1,2,1,2],3)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=DESERT;f[12:17,8:56]=DUNE
  for i in range(len(x["deps"])):p=7+i*8;f[23:32,p:p+6]=DONE if g.done&(1<<i) else WALKER
  f[40:44,8:8+sum(g.history[-2:])*6]=POLICY;f[51:56,7+g.cursor*8:13+g.cursor*8]=CURSOR
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q485(ARCBaseGame):
 def __init__(self):self.display=D(self);self.done=self.cursor=self.completed=0;self.history=[];self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q485",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,5,6])
 def on_set_level(self,l):self.done=self.cursor=self.completed=0;self.history=[];self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index];n=len(x["deps"])
  if z==0:self.complete_action();return
  if z==1:self.cursor=(self.cursor-1)%n
  elif z==2:self.cursor=(self.cursor+(2 if self.completed>=x["rewire"] else 1))%n
  elif z==5 and not self.done&(1<<self.cursor) and all(self.done&(1<<d) for d in x["deps"][self.cursor]):
   policy=x["policies"][self.cursor]
   if len(self.history)>=2 and self.history[-1]==self.history[-2]==policy:self.bad=True;self.lose()
   else:self.history.append(policy);self.done|=1<<self.cursor;self.completed+=1
  elif z==6:
   if self.done==(1<<n)-1:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
