"""q209 Tidal Mosaic -- track physical tiles through a rotating tidal viewport."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAGOON,TILE,TIDE,VIEW,MARK,BAD=0,10,12,9,15,11,8
LEVELS=[{"name":n,"span":s,"plan":p} for n,s,p in [
 ("First Tile",5,(3,1,3)),("Rotated Window",6,(2,3,1,3)),("Reverse Tide",7,(1,3,2,3,1)),
 ("Four Cell Current",8,(2,1,3,3,2,1)),("Mosaic Parity",9,(3,1,2,3,1,3,2)),
 ("Tidal Mosaic",10,(2,3,1,2,3,3,1,2))]]
def advance(state,a,span):
 vals,view,tide=state;v=list(vals)
 if a==1:view=(view+1)%4
 elif a==2:tide=1-tide
 else:
  physical=(view+(2 if tide else 0))%4;v[physical]=(v[physical]+(1 if tide==0 else -1))%span
 return tuple(v),view,tide
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=LAGOON
  for i,v in enumerate(g.vals):
   x=8+(i%2)*28;y=11+(i//2)*22;f[y:y+15,x:x+15]=TILE;f[y+4:y+9,x+3:x+3+v]=MARK
  f[50:54,8:8+g.view*10]=VIEW;f[55:58,43:56]=TIDE if g.tide else MARK
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q209(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.vals=(0,1,2,3);self.view=self.tide=0;self.target=None;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q209",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.vals=(0,1,2,3);self.view=self.tide=0;s=(self.vals,0,0)
  for a in x["plan"]:s=advance(s,a,x["span"])
  self.target=s;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.vals,self.view,self.tide=advance((self.vals,self.view,self.tide),a,x["span"])
  elif a==6:
   if (self.vals,self.view,self.tide)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
