"""q391 Tapestry Delegation -- persistent complementary marks followed by rewired choice."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LOOM,THREAD,TENSION,MARK,REWIRE,CURSOR,BAD=14,9,12,13,15,10,6,8
LEVELS=[{"name":n,"clues":c} for n,c in [("Split Loom",[0,1]),("Persistent Thread",[1,1]),("Alternating View",[1,0]),("Rewired Choice",[0,0]),("Integrated Pattern",[1,0]),("Tapestry Delegation",[0,1])]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=LOOM;f[13:18,8:56]=THREAD;f[26:31,8:56]=TENSION;f[38:42,8:8+g.marks*7]=MARK
  if g.marks:f[46:50,8:56:2]=REWIRE
  f[53:57,9+g.cursor*17:20+g.cursor*17]=CURSOR
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q391(ARCBaseGame):
 def __init__(self):self.display=D(self);self.controller=self.marks=self.cursor=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q391",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,6])
 def on_set_level(self,l):self.controller=self.marks=self.cursor=0;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z==1:self.marks|=1<<(self.controller*2+x["clues"][self.controller])
  elif z==2:self.controller=1-self.controller
  elif z==3:self.cursor=(self.cursor+(2 if self.marks else 1))%3
  elif z==6:
   if all(self.marks&(1<<(i*2+x["clues"][i])) for i in range(2)) and self.cursor==(x["clues"][0]^x["clues"][1]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
