"""q371 Pollen Rig -- assemble reusable bloom hardware across a visible rule complement."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,BLOOM,RIG,PHASE,WEAR,RULE,BAD=6,14,11,15,12,10,9,8
LEVELS=[
 {"name":"First Redirect","mod":3,"boundary":2,"recipe":((1,0),)},
 {"name":"Complement Joint","mod":4,"boundary":2,"recipe":((2,1),(1,0))},
 {"name":"Worn Support","mod":5,"boundary":3,"recipe":((3,2),(2,4))},
 {"name":"Bloom Geometry","mod":5,"boundary":3,"recipe":((1,4),(3,2),(2,4))},
 {"name":"Reusable Pollen Rig","mod":6,"boundary":4,"recipe":((2,3),(1,2),(3,5),(2,0))},
 {"name":"Pollen Rig","mod":7,"boundary":5,"recipe":((3,5),(1,5),(2,1),(3,0),(1,0))}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=MEADOW
  for i,c in enumerate(x["recipe"]):
   y=9+i*8;f[y:y+5,8:25]=BLOOM;f[y+1:y+4,10:10+c[0]*3]=RIG
  f[13:17,38:38+g.phase*3]=PHASE;f[27:31,38:38+g.wear*3]=WEAR;f[41:45,38:55]=RULE if g.declared else MEADOW;f[48:53,38:38+g.selected*5]=RIG
  if g.wear>=x["boundary"]:f[7:10,8:56]=WEAR
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q371(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.phase=self.wear=self.declared=self.selected=0;self.built=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q371",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.phase=self.wear=self.declared=self.selected=0;self.built=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.selected=a
  elif a==5:self.phase=(self.phase+1)%x["mod"];self.wear+=1
  elif a==6:self.declared^=1
  elif a==4:
   component,target=x["recipe"][len(self.built)] if len(self.built)<len(x["recipe"]) else (-1,-1);changed=self.wear>=x["boundary"];actual=4-self.selected if changed else self.selected
   if actual==component and self.phase==target and self.declared==int(changed):
    self.built.append(component);self.phase=(self.phase+component+1)%x["mod"];self.wear+=1
    if len(self.built)==len(x["recipe"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
