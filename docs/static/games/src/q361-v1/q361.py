"""q361 Reef Assembly -- weld reusable modules only at compatible tide phases."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REEF,MODULE,SELECTED,WELD,TIDE,BAD=2,9,11,14,15,6,8
LEVELS=[{"name":n,"mod":m,"recipe":r,"heats":h} for n,m,r,h in [
 ("Shell Clamp",3,(1,),(0,)),("Twin Brace",4,(1,2),(1,3)),
 ("Coral Joint",4,(3,1),(2,0)),("Reusable Frame",5,(2,3,1),(1,4,2)),
 ("Tidal Workshop",5,(3,2,1,3),(2,0,3,1)),("Reef Assembly",6,(1,3,2,1,2),(4,1,5,2,0))]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=REEF
  for i in range(3):
   x=9+i*17;f[12:23,x:x+11]=SELECTED if g.selected==i+1 else MODULE
  for i,a in enumerate(g.built):f[30:39,8+i*9:15+i*9]=WELD if a%2 else MODULE
  f[49:54,8:8+g.heat*8]=TIDE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q361(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.selected=self.heat=0;self.built=[];self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q361",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5])
 def on_set_level(self,l):self.selected=self.heat=0;self.built=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.selected=a
  elif a==5:self.heat=(self.heat+1)%x["mod"]
  elif a==4:
   i=len(self.built)
   if i<len(x["recipe"]) and self.selected==x["recipe"][i] and self.heat==x["heats"][i]:
    self.built.append(self.selected);self.heat=(self.heat+self.selected)%x["mod"];self.selected=0
    if len(self.built)==len(x["recipe"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
