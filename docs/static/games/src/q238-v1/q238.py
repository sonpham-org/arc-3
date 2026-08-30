"""q238 Signal Banquet -- infer etiquette from ordered invitations and replies."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TABLE,GUEST,INVITE,REPLY,RULE,BAD=1,12,15,6,14,10,8
REPLIES=((1,2,3,1),(2,1,1,3),(3,3,2,1),(1,3,1,2))
LEVELS=[{"name":n,"rule":r,"invites":seq} for n,r,seq in [
 ("Host Signal",0,(1,)),("Paired Seats",1,(2,1)),("Late Guest",2,(1,3,2)),
 ("Reciprocal Course",3,(4,2,1)),("Seating Revision",1,(3,1,4,2)),
 ("Signal Banquet",2,(2,4,1,3,2))]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=TABLE
  for i in range(4):
   x=7+i*14;f[11:23,x:x+10]=INVITE if i+1 in g.history else GUEST
  for i,v in enumerate(g.transcript):f[30+i*4:33+i*4,8:8+v*10]=REPLY
  f[52:56,8:8+g.candidate*11]=RULE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q238(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.history=[];self.transcript=[];self.candidate=0;self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q238",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.history=[];self.transcript=[];self.candidate=0;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.history.append(a);self.transcript.append(REPLIES[x["rule"]][a-1])
  elif a==5:self.candidate=(self.candidate+1)%4
  elif a==6:
   if tuple(self.history)==x["invites"] and self.candidate==x["rule"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
