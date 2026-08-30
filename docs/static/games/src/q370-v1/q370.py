"""q370 Vault Rig -- assemble reusable echo hardware while balancing two coupled resource rings."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,ECHO,RIG,PHASEA,PHASEB,DONE,BAD=6,9,11,15,14,12,10,8
LEVELS=[
 {"name":"First Redirect","ma":3,"mb":4,"recipe":((1,0,0),)},
 {"name":"Joined Echo","ma":4,"mb":5,"recipe":((2,1,2),(1,0,1))},
 {"name":"Supported Carrier","ma":5,"mb":5,"recipe":((3,2,1),(2,0,4))},
 {"name":"Coupled Geometry","ma":5,"mb":6,"recipe":((1,4,2),(3,1,5),(2,3,0))},
 {"name":"Reusable Rig","ma":6,"mb":7,"recipe":((2,3,4),(1,0,2),(3,5,1),(2,2,6))},
 {"name":"Vault Rig","ma":7,"mb":8,"recipe":((3,5,6),(1,2,1),(2,6,4),(3,0,7),(1,4,2))}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=VAULT
  for i,c in enumerate(x["recipe"]):
   y=9+i*8;f[y:y+5,8:25]=DONE if i<len(g.built) else ECHO;f[y+1:y+4,10:10+c[0]*3]=RIG
  f[13:17,38:38+g.a*3]=PHASEA;f[27:31,38:38+g.b*2]=PHASEB;f[45:51,38:38+g.selected*5]=RIG
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q370(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.a=self.b=self.selected=0;self.built=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q370",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.a=self.b=self.selected=0;self.built=[];self.bad=False
 def step(self):
  action=self.action.id.value;x=LEVELS[self.level_index]
  if action==0:self.complete_action();return
  if action in (1,2,3):self.selected=action
  elif action==5:self.a=(self.a+1)%x["ma"]
  elif action==6:self.b=(self.b+1)%x["mb"]
  elif action==4:
   need=x["recipe"][len(self.built)] if len(self.built)<len(x["recipe"]) else None
   if need==(self.selected,self.a,self.b):
    self.built.append(self.selected);self.a=(self.a+self.selected)%x["ma"];self.b=(self.b+2*self.selected)%x["mb"]
    if len(self.built)==len(x["recipe"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
