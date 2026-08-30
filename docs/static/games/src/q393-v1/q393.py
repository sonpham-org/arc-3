"""q393 Submarine Chorus -- combine partial tones through ordered acoustic relays."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,OCEAN,SUB,TONE,RELAY,CODE,BAD=7,9,14,11,15,12,8
LEVELS=[{"name":n,"tones":t,"flow":f,"target":c} for n,t,f,c in [
 ("First Ping",(1,2),(1,2,3),1),("Return Echo",(2,3),(2,1,4),2),
 ("Depth Split",(3,1),(1,3,2,4),3),("Compressed Chorus",(1,3),(2,4,1,3),0),
 ("Crossed Sonar",(2,2),(1,2,3,4,3),2),("Submarine Chorus",(3,3),(2,1,4,3,4,3),1)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=OCEAN;f[12:26,7:25]=SUB;f[12:26,39:57]=SUB
  f[16:21,12:20]=TONE if g.seen&1 else OCEAN;f[16:21,44:52]=TONE if g.seen&2 else OCEAN
  for i,v in enumerate(g.shared[-4:]):f[32+i*5:36+i*5,8:8+v*10]=RELAY
  f[53:57,8:8+g.candidate*11]=CODE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q393(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mem=[0,0];self.seen=self.candidate=0;self.shared=[];self.history=[];self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q393",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mem=[0,0];self.seen=self.candidate=0;self.shared=[];self.history=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.mem[0]=x["tones"][0];self.seen|=1;self.history.append(a)
  elif a==2:self.mem[1]=x["tones"][1];self.seen|=2;self.history.append(a)
  elif a==3:self.shared.append((2*self.mem[0]+self.mem[1])%4);self.history.append(a)
  elif a==4:self.shared.append((self.mem[0]+2*self.mem[1])%4);self.history.append(a)
  elif a==5:self.candidate=(self.candidate+1)%4
  elif a==6:
   if tuple(self.history)==x["flow"] and self.seen==3 and self.candidate==x["target"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
