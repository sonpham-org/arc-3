"""q331 Lantern Census -- accumulate map evidence while scan orientation changes at base."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,DISTRICT,LANTERN,KNOWN,CHARGE,WELL,BAD=4,12,11,15,14,9,8
MASKS=(0b00110101,0b11001010,0b10100110)
LEVELS=[{"name":n,"solution":s,"capacity":c} for n,s,c in [
 ("Street Count",(1,),1),("Turning Census",(1,2),1),("Reoriented Blocks",(3,1),1),
 ("Shared Lantern",(2,3,1),2),("Sparse Markers",(1,3,2),1),("Lantern Census",(3,2,1,3),1)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=DISTRICT
  for i in range(8):
   x=8+(i%4)*13;y=11+(i//4)*16;f[y:y+10,x:x+10]=KNOWN if g.known&(1<<i) else WELL
  f[44:48,8:8+g.charge*13]=CHARGE;f[51:56,8:8+g.orientation*15]=LANTERN
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q331(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.known=self.selected=self.orientation=0;self.charge=1;self.target=0;self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q331",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.known=self.selected=self.orientation=0;self.charge=x["capacity"];self.bad=False;o=0;t=0
  for a in x["solution"]:t|=MASKS[(a-1+o)%3];o=(o+1)%3
  self.target=t
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.selected=a
  elif a==4:
   if self.selected and self.charge:self.known|=MASKS[(self.selected-1+self.orientation)%3];self.charge-=1;self.selected=0
   else:self.bad=True;self.lose()
  elif a==5:self.orientation=(self.orientation+1)%3;self.charge=x["capacity"];self.selected=0
  elif a==6:
   if self.known==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
