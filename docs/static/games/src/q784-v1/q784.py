"""q784 Moraine Rhythm -- macro-time glacier alignment coupled to an outer token."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GLACIER,STONE,CREVASSE,CLOCKA,CLOCKB,TOKEN,BAD=4,10,12,14,15,13,6,8
LEVELS=[{"name":n,"mods":m,"target":t,"chunks":c,"token":k} for n,m,t,c,k in [("Raft Pulse",[4,5],[2,3],1,1),("Flow Band",[5,7],[4,1],1,2),("Macro Drift",[6,7],[1,5],2,1),("Interrupt Crevasse",[7,8],[6,2],1,3),("Outer Token",[8,9],[3,7],2,2),("Moraine Rhythm",[9,11],[8,6],3,3)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=GLACIER;f[13:18,8:56]=CREVASSE;f[24:34,9:21]=STONE;f[40:44,8:8+g.phase[0]*5]=CLOCKA;f[47:51,8:8+g.phase[1]*4]=CLOCKB;f[54:58,8:8+g.token*10]=TOKEN
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q784(ARCBaseGame):
 def __init__(self):self.display=D(self);self.phase=[0,0];self.chunks=self.token=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q784",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[2,3,4,5,6])
 def on_set_level(self,l):self.phase=[0,0];self.chunks=self.token=0;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z==2:self.token=(self.token+1)%4
  elif z==3:self.phase[0]=(self.phase[0]+1)%x["mods"][0]
  elif z==4:self.phase[1]=(self.phase[1]+1)%x["mods"][1]
  elif z==5:self.phase=[(self.phase[i]+3)%x["mods"][i] for i in range(2)];self.chunks+=1
  elif z==6:
   if self.phase==x["target"] and self.chunks>=x["chunks"] and self.token==x["token"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
