"""q216 Backstage Veil -- freeze one scene while hidden actors and a signed meter evolve."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,THEATER,SCENE,ACTOR,FOCUS,METER,GOAL,BAD=0,7,11,15,14,12,10,8
LEVELS=[
 {"name":"First Sightline","plan":(1,4,2)},{"name":"Signed Offer","plan":(2,5,1,4)},
 {"name":"Hidden Cast","plan":(3,4,2,5,1)},{"name":"Threshold Scene","plan":(1,4,1,5,3,4)},
 {"name":"Directional Meter","plan":(2,5,2,4,3,5,1)},{"name":"Backstage Veil","plan":(3,4,5,1,5,2,4,3)}]
def advance(s,a):
 actors,focus,meter,direction=s;actors=list(actors)
 if a in (1,2,3):
  focus=a-1
  for i in range(3):
   if i!=focus:actors[i]=(actors[i]+i+1+abs(meter))%4
 else:
  direction=1 if a==4 else -1;meter=max(-6,min(6,meter+direction*(focus+1)));actors[focus]=(actors[focus]+direction)%4
 return tuple(actors),focus,meter,direction
def target(x):
 s=((0,1,2),0,0,1)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=THEATER
  for i,v in enumerate(g.actors):
   x=8+i*18;f[10:39,x:x+14]=SCENE;f[31-v*5:36,x+3:x+11]=ACTOR
   if i==g.focus:f[7:10,x:x+14]=FOCUS
  start=31;end=max(8,min(56,start+g.meter*4));f[46:51,min(start,end):max(start,end)+1]=METER;f[54:58,8:29 if g.direction>0 else 16]=GOAL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q216(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.actors=(0,1,2);self.focus=self.meter=0;self.direction=1;self.target=target(LEVELS[0]);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q216",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.actors=(0,1,2);self.focus=self.meter=0;self.direction=1;self.target=target(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.actors,self.focus,self.meter,self.direction=advance((self.actors,self.focus,self.meter,self.direction),a)
  elif a==6:
   if (self.actors,self.focus,self.meter,self.direction)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
