"""q300 Aquifer Tithe -- preserve weighted water through pumping and phase change."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,AQUIFER,WATER,VAPOR,VALVE,AUDIT,BAD=3,10,9,15,11,14,8
LEVELS=[{"name":n,"total":t,"plan":p} for n,t,p in [
 ("First Pump",4,(1,2)),("Vapor Return",5,(1,2,3)),("Double Valve",6,(4,1,2,3)),
 ("Closed Basin",7,(1,4,1,2,2,3)),("Tithe Ledger",8,(4,1,2,1,3,2,3)),
 ("Aquifer Tithe",9,(1,4,1,2,2,3,4,2,3))]]
def advance(state,a):
 wells,vapor,phase=state;w=list(wells);amount=1+phase
 if a==1:
  d=min(w[0],amount);w[0]-=d;w[1]+=d
 elif a==2:
  d=min(w[1],amount);w[1]-=d;vapor+=d
 elif a==3:
  d=min(vapor,amount);vapor-=d;w[0]+=d
 else:phase=1-phase
 return tuple(w),vapor,phase
def simulate(total,plan):
 s=((total,0),0,0)
 for a in plan:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=AQUIFER
  for i,v in enumerate(g.wells):
   x=9+i*25;f[15:45,x:x+17]=VALVE;f[43-v*3:43,x+2:x+15]=WATER
  f[8:12,8:8+g.vapor*5]=VAPOR;f[49:53,8:8+g.phase*19]=AUDIT
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q300(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.wells=(1,0);self.vapor=self.phase=self.audits=0;self.target=None;self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q300",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.wells=(x["total"],0);self.vapor=self.phase=self.audits=0;self.target=simulate(x["total"],x["plan"]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.wells,self.vapor,self.phase=advance((self.wells,self.vapor,self.phase),a)
  elif a==5:
   if sum(self.wells)+self.vapor==x["total"]:self.audits+=1
   else:self.bad=True;self.lose()
  elif a==6:
   if (self.wells,self.vapor,self.phase)==self.target and self.audits>=2:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
