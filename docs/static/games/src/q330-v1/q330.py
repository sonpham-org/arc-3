"""q330 Echo Cartography -- budget beacon pulses while keeping recovered map knowledge."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CAVE,BEACON,ECHO,KNOWLEDGE,CHARGE,BAD=4,8,14,12,15,10,3
MASKS=(0b001011,0b110010,0b101100)
LEVELS=[{"name":n,"need":need,"solution":sol,"charge":c} for n,need,sol,c in [
 ("First Echo",0b001011,(1,),1),("Overlapping Cavern",0b111011,(1,2),1),
 ("Return to Base",0b111110,(2,3),1),("Sparse Survey",0b111111,(1,2,3),2),
 ("Echo Budget",0b111111,(3,1,2),1),("Echo Cartography",0b111111,(2,1,3,2),1)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=CAVE
  for i in range(6):
   x=9+(i%3)*17;y=12+(i//3)*17;f[y:y+10,x:x+10]=KNOWLEDGE if g.known&(1<<i) else ECHO
  f[48:52,8:8+g.charge*12]=CHARGE
  if g.selected:f[54:58,8:8+g.selected*13]=BEACON
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q330(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.known=self.selected=0;self.charge=1;self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q330",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.known=self.selected=0;self.charge=x["charge"];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.selected=a
  elif a==4:
   if self.selected and self.charge:self.known|=MASKS[self.selected-1];self.charge-=1;self.selected=0
   else:self.bad=True;self.lose()
  elif a==5:self.charge=x["charge"];self.selected=0
  elif a==6:
   if self.known&x["need"]==x["need"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
