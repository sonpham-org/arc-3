"""q218 Asterism Veil -- schedule attention, then reset physical stars while preserving evidence."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SPACE,STAR,LINE,FOCUS,EVIDENCE,RESET,BAD=0,3,15,11,14,12,10,8
LEVELS=[
 {"name":"First Veil","plan":(1,4,5,2)},{"name":"Preserved Chart","plan":(2,1,4,5,3)},
 {"name":"Hidden Orbit","plan":(3,2,4,5,1,2)},{"name":"Reset Sightline","plan":(1,3,2,4,5,2,1)},
 {"name":"Precessing Evidence","plan":(2,1,3,4,5,3,2,1)},{"name":"Asterism Veil","plan":(3,1,2,3,4,5,1,3,2)}]
def run(x):
 cells=[0,1,2];focus=0;evidence=0;reset=False
 for a in x["plan"]:
  if a in (1,2,3):
   focus=a-1
   for i in range(3):
    if i!=focus:cells[i]=(cells[i]+i+1)%4
  elif a==4:evidence=(cells[0]+2*cells[1]+3*cells[2])%7
  else:cells=[0,1,2];reset=True
 return tuple(cells),focus,evidence,reset
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SPACE
  for i,v in enumerate(g.cells):
   x=9+i*17;f[11:29,x:x+11]=LINE;f[15+v*2:21+v*2,x+3:x+8]=STAR
   if i==g.focus:f[8:11,x:x+11]=FOCUS
  f[39:44,8:8+g.evidence*7]=EVIDENCE;f[50:55,8:29 if g.reset_done else 16]=RESET
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q218(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.cells=[0,1,2];self.focus=self.evidence=0;self.reset_done=False;self.target=run(LEVELS[0]);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q218",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.cells=[0,1,2];self.focus=self.evidence=0;self.reset_done=False;self.target=run(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3):
   self.focus=a-1
   for i in range(3):
    if i!=self.focus:self.cells[i]=(self.cells[i]+i+1)%4
  elif a==4:self.evidence=(self.cells[0]+2*self.cells[1]+3*self.cells[2])%7
  elif a==5:self.cells=[0,1,2];self.reset_done=True
  elif a==6:
   if (tuple(self.cells),self.focus,self.evidence,self.reset_done)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
