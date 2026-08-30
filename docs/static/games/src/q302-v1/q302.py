"""q302 Seed Exchange -- conserve crop units through planting, growth, and harvest."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FARM,SEED,SPROUT,FLOWER,SEASON,AUDIT,BAD=3,14,11,10,15,12,9,8
LEVELS=[
 {"name":"First Planting","stock":4,"plan":(1,2)},{"name":"Harvest Return","stock":5,"plan":(1,2,3)},
 {"name":"Double Season","stock":6,"plan":(4,1,2,3)},{"name":"Closed Field","stock":7,"plan":(1,4,1,2,2,3)},
 {"name":"Seed Ledger","stock":8,"plan":(4,1,2,1,3,2,3)},{"name":"Seed Exchange","stock":9,"plan":(1,4,1,2,2,3,4,2,3)}]
def advance(state,a):
 bins,season=state;b=list(bins);amount=1+season
 if a in (1,2,3):
  src=a-1;dst=a%3;d=min(b[src],amount);b[src]-=d;b[dst]+=d
 else:season=1-season
 return tuple(b),season
def simulate(stock,plan):
 s=((stock,0,0),0)
 for a in plan:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=FARM
  for i,(v,c) in enumerate(zip(g.bins,(SEED,SPROUT,FLOWER))):
   x=8+i*17;f[13:43,x:x+12]=AUDIT;f[41-v*3:41,x+2:x+10]=c
  f[49:53,8:8+g.season*19]=SEASON;f[54:58,8:8+g.audits*12]=AUDIT
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q302(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bins=(1,0,0);self.season=self.audits=0;self.target=None;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q302",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.bins=(x["stock"],0,0);self.season=self.audits=0;self.target=simulate(x["stock"],x["plan"]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.bins,self.season=advance((self.bins,self.season),a)
  elif a==5:
   if sum(self.bins)==x["stock"]:self.audits+=1
   else:self.bad=True;self.lose()
  elif a==6:
   if (self.bins,self.season)==self.target and self.audits>=2:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
