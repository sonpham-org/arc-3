"""q783 Murmuration Rhythm -- macro-time alignment with a redundant parity audit."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,AVIARY,BIRD,WAKE,CLOCKA,CLOCKB,PARITY,BAD=3,7,13,10,14,12,6,8
LEVELS=[{"name":n,"mods":m,"target":t,"chunks":c,"signals":s,"bad":b} for n,m,t,c,s,b in [
 ("Flock Pulse",[4,5],[2,3],1,[1,0,1],1),("Unequal Wake",[5,7],[4,1],1,[0,1,1],2),("Macro Flight",[6,7],[1,5],2,[1,1,0,1],0),
 ("Interrupt Window",[7,8],[6,2],1,[0,1,0,1],3),("Parity Beat",[8,9],[3,7],2,[1,0,1,1,0],4),("Murmuration Rhythm",[9,11],[8,6],3,[1,1,0,1,0,0],2)]]
def parity(x):return sum(v^(i==x["bad"]) for i,v in enumerate(x["signals"]))%2
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=AVIARY;f[14:24,8:56]=BIRD;f[29:34,8:56]=WAKE;f[39:43,8:8+g.phase[0]*5]=CLOCKA;f[46:50,8:8+g.phase[1]*4]=CLOCKB;f[53:57,8:8+g.claim*18]=PARITY
  if g.badstate:f[61:64,22:42]=BAD
  return f
class Q783(ARCBaseGame):
 def __init__(self):self.display=D(self);self.phase=[0,0];self.chunks=self.claim=0;self.badstate=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q783",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[2,3,4,5,6])
 def on_set_level(self,l):self.phase=[0,0];self.chunks=self.claim=0;self.badstate=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z==2:self.claim=1-self.claim
  elif z==3:self.phase[0]=(self.phase[0]+1)%x["mods"][0]
  elif z==4:self.phase[1]=(self.phase[1]+1)%x["mods"][1]
  elif z==5:self.phase=[(self.phase[i]+3)%x["mods"][i] for i in range(2)];self.chunks+=1
  elif z==6:
   if self.phase==x["target"] and self.chunks>=x["chunks"] and self.claim==parity(x):self.next_level()
   else:self.badstate=True;self.lose()
  else:self.badstate=True;self.lose()
  self.complete_action()
