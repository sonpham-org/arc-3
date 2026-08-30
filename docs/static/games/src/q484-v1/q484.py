"""q484 Moraine Dependency -- order-sensitive nested glacier prerequisites."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GLACIER,STONE,CREVASSE,DONE,TOKEN,CURSOR,BAD=3,10,12,14,15,13,6,8
LEVELS=[{"name":n,"deps":d,"order":o,"mod":m,"rewire":r} for n,d,o,m,r in [("Inner Enclosure",[[],[0],[0]],[0,1,2],5,1),("Shared Raft",[[],[0],[0],[1,2]],[0,2,1,3],7,2),("Outer Token",[[],[0],[1],[0],[2,3]],[0,1,2,3,4],7,2),("Flow Bands",[[],[],[0,1],[1],[2,3]],[1,0,3,2,4],9,3),("Reused Enclosure",[[],[0],[0],[1,2],[2],[3,4]],[0,2,1,4,3,5],11,3),("Moraine Dependency",[[],[],[0],[0,1],[2,3],[1,4]],[1,0,2,3,4,5],13,3)]]
def checksum(order,mod):
 x=0
 for v in order:x=(x*3+v+1)%mod
 return x
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=GLACIER;f[12:17,8:56]=CREVASSE
  for i in range(len(x["deps"])):p=7+i*8;f[23:32,p:p+6]=DONE if g.done&(1<<i) else STONE
  f[39:44,8:8+g.token*4]=TOKEN;f[51:56,7+g.cursor*8:13+g.cursor*8]=CURSOR
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q484(ARCBaseGame):
 def __init__(self):self.display=D(self);self.done=self.cursor=self.completed=self.token=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q484",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,5,6])
 def on_set_level(self,l):self.done=self.cursor=self.completed=self.token=0;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index];n=len(x["deps"])
  if z==0:self.complete_action();return
  if z==1:self.cursor=(self.cursor-1)%n
  elif z==2:self.cursor=(self.cursor+(2 if self.completed>=x["rewire"] else 1))%n
  elif z==5 and not self.done&(1<<self.cursor) and all(self.done&(1<<d) for d in x["deps"][self.cursor]):self.done|=1<<self.cursor;self.completed+=1;self.token=(self.token*3+self.cursor+1)%x["mod"]
  elif z==6:
   if self.done==(1<<n)-1 and self.token==checksum(x["order"],x["mod"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
