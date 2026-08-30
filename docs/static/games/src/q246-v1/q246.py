"""q246 Backstage Pact -- infer a convention while offers push a thresholded shared meter."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,THEATER,ACTOR,OFFER,METER,ROLE,STAKE,BAD=1,11,15,14,12,10,13,8
LEVELS=[
 {"name":"First Offer","role":0,"threshold":1,"plan":(1,)},{"name":"Recency Scene","role":1,"threshold":2,"plan":(1,2)},
 {"name":"Reciprocal Scene","role":2,"threshold":3,"plan":(2,3)},{"name":"Rotating Cast","role":1,"threshold":4,"plan":(1,2,3)},
 {"name":"Crossed Offers","role":0,"threshold":5,"plan":(3,1,2,3)},{"name":"Backstage Pact","role":2,"threshold":4,"plan":(2,3,1,2,1)}]
def bid(role,a,previous):
 if role==0:return a
 if role==1:return (previous+a)%4
 return (4-a+previous)%4
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=THEATER
  for i in range(3):
   x=9+i*17;f[11:25,x:x+11]=OFFER if g.seen&(1<<i) else ACTOR
  for i,v in enumerate(g.offers[-5:]):f[30+i*4:33+i*4,8:8+v*11]=METER
  f[50:53,8:8+g.meter*3]=METER;f[54:57,8:8+g.role*14]=ROLE;f[58:61,8:8+g.stake*8]=STAKE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q246(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.seen=self.meter=self.role=self.stake=0;self.offers=[];self.history=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q246",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.seen=self.meter=self.role=self.stake=0;self.offers=[];self.history=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):
   self.seen|=1<<(a-1);v=bid(x["role"],a,self.offers[-1] if self.offers else 0);self.offers.append(v);self.meter=(self.meter+v+a)%13;self.history.append(a)
  elif a==4:self.role=(self.role+1)%3
  elif a==5:self.stake=(self.stake+1)%6
  elif a==6:
   direction=1 if self.meter>=x["threshold"] else 0
   if tuple(self.history)==x["plan"] and self.role==x["role"] and self.stake==x["threshold"] and direction:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
