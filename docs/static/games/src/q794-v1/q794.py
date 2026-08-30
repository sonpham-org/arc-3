"""q794 Tessera Rhythm -- compress seam routines but interrupt the macro at a state-defined window."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MOSAIC,TESSERA,RHYTHM,WINDOW,SEAM,CLAIM,BAD=12,3,15,14,11,9,13,8
LEVELS=[
 {"name":"First Interrupt","period":4,"window":1,"plan":(3,2),"claim":1},{"name":"Compressed Fold","period":5,"window":3,"plan":(4,2,3),"claim":1},
 {"name":"Scaled Seam","period":6,"window":2,"plan":(1,3,2),"claim":1},{"name":"Topology Window","period":7,"window":3,"plan":(3,3,1,2),"claim":2},
 {"name":"Interrupted Mosaic","period":8,"window":6,"plan":(1,3,4,1,2),"claim":1},{"name":"Tessera Rhythm","period":9,"window":7,"plan":(3,4,3,1,1,2,4),"claim":2}]
def simulate(x):
 phase=seam=0;caught=False
 for a in x["plan"]:
  if a==1:phase=(phase+1)%x["period"]
  elif a==2:caught|=phase==x["window"]
  elif a==3:seam=(seam+1)%4;phase=(phase+1)%x["period"]
  else:phase=(phase+3)%x["period"]
 return phase,caught,seam
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MOSAIC
  for i in range(4):f[11:27,8+i*13:18+i*13]=WINDOW if i==g.phase%4 else TESSERA
  f[31:35,8:8+g.phase*5]=RHYTHM;f[39:43,8:8+g.seam*12]=SEAM;f[47:51,8:29 if g.caught else 16]=WINDOW;f[54:58,8:8+g.claim*12]=CLAIM
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q794(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.phase=self.seam=self.claim=0;self.caught=False;self.history=[];self.target=(0,False,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q794",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.phase=self.seam=self.claim=0;self.caught=False;self.history=[];self.target=simulate(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.phase=(self.phase+1)%x["period"];self.history.append(a)
  elif a==2:self.caught|=self.phase==x["window"];self.history.append(a)
  elif a==3:self.seam=(self.seam+1)%4;self.phase=(self.phase+1)%x["period"];self.history.append(a)
  elif a==4:self.phase=(self.phase+3)%x["period"];self.history.append(a)
  elif a==5:self.claim=(self.claim+1)%4
  elif a==6:
   if tuple(self.history)==x["plan"] and (self.phase,self.caught,self.seam)==self.target and self.caught and self.claim==x["claim"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
