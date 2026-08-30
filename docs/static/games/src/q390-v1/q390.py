"""q390 Spore Delegation -- complementary marks made only at sparse shared events."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,SPORE,HUMIDITY,MARK,CLOCK,CONTROL,BAD=10,2,13,12,15,14,6,8
LEVELS=[{"name":n,"clues":c,"mods":m} for n,c,m in [("Split View",[0,1],[2,3]),("Persistent Mark",[1,1],[3,4]),("Sparse Event",[1,0],[4,5]),("Unequal Actors",[0,0],[5,6]),("Integrated View",[1,0],[6,7]),("Spore Delegation",[0,1],[7,8])]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=GREENHOUSE;f[13:25,8:22]=SPORE;f[13:25,42:56]=SPORE;f[30:35,8:56]=HUMIDITY;f[40:44,8:8+g.marks*7]=MARK;f[48:52,8:8+sum(g.phase)*4]=CLOCK;f[54:57,8+g.controller*32:24+g.controller*32]=CONTROL
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q390(ARCBaseGame):
 def __init__(self):self.display=D(self);self.phase=[0,0];self.controller=self.marks=self.candidate=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q390",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.phase=[0,0];self.controller=self.marks=self.candidate=0;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z==1 and self.phase==[0,0]:self.marks|=1<<(self.controller*2+x["clues"][self.controller]);self.phase=[1%x["mods"][0],2%x["mods"][1]]
  elif z==2:self.controller=1-self.controller
  elif z==3:self.phase[0]=(self.phase[0]+1)%x["mods"][0]
  elif z==4:self.phase[1]=(self.phase[1]+1)%x["mods"][1]
  elif z==5:self.candidate=1-self.candidate
  elif z==6:
   if all(self.marks&(1<<(i*2+x["clues"][i])) for i in range(2)) and self.candidate==(x["clues"][0]^x["clues"][1]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
