"""q392 Observatory Relay -- merge partial sky memories through directional relays."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,DOME,STAR,MEMORY,RELAY,CANDIDATE,BAD=13,1,6,15,10,12,14,8
LEVELS=[{"name":n,"clues":c,"flow":f,"target":t} for n,c,f,t in [
 ("Two Domes",(1,2),(1,2,3),1),("Return Signal",(2,3),(1,2,4),2),
 ("Asymmetric Relay",(3,1),(2,1,3,4),3),("Memory Merge",(1,3),(1,3,2,4),0),
 ("Crossed Baseline",(2,2),(2,4,1,3,4),2),("Observatory Relay",(3,3),(1,2,3,4,3,4),1)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SKY;f[11:29,7:26]=DOME;f[11:29,38:57]=DOME
  f[16:22,13:19]=MEMORY if g.seen&1 else STAR;f[16:22,44:50]=MEMORY if g.seen&2 else STAR
  f[33:38,8:8+g.transfers*9]=RELAY;f[48:53,8:8+g.candidate*11]=CANDIDATE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q392(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mem=[0,0];self.seen=self.transfers=self.candidate=0;self.history=[];self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q392",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mem=[0,0];self.seen=self.transfers=self.candidate=0;self.history=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.mem[0]=x["clues"][0];self.seen|=1
  elif a==2:self.mem[1]=x["clues"][1];self.seen|=2
  elif a==3:self.mem[1]=(self.mem[1]+self.mem[0])%4;self.transfers+=1
  elif a==4:self.mem[0]=(self.mem[0]^self.mem[1])%4;self.transfers+=1
  elif a==5:self.candidate=(self.candidate+1)%4
  elif a==6:
   if tuple(self.history)==tuple(x["flow"]) and self.seen==3 and self.candidate==x["target"]:self.next_level()
   else:self.bad=True;self.lose()
   self.complete_action();return
  else:self.bad=True;self.lose()
  if a in (1,2,3,4):self.history.append(a)
  self.complete_action()
