"""q299 Glasshouse Balance -- route conserved heat through phase-sensitive valves."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GLASS,VESSEL,HEAT,COLD,PHASE,AUDIT,BAD=1,10,6,12,9,15,11,8
LEVELS=[{"name":n,"total":t,"plan":p} for n,t,p in [
 ("Warm Transfer",4,[1,1,2]),("Cold Return",5,[1,4,2,3]),
 ("Phase Valve",6,[1,2,4,2,3]),("Balanced Bays",7,[1,1,4,2,3,2]),
 ("Thermal Ledger",8,[1,4,1,2,3,4,2]),("Glasshouse Balance",9,[1,1,4,2,2,3,4,1])]]
def move(v,a,phase):
 v=list(v);src,dst=((0,1),(1,2),(2,0))[a-1];amount=min(v[src],1+phase)
 v[src]-=amount;v[dst]+=amount;return tuple(v)
def simulate(total,plan):
 v=(total,0,0);phase=0
 for a in plan:
  if a==4:phase=1-phase
  else:v=move(v,a,phase)
 return v,phase
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GLASS
  for i,v in enumerate(g.vessels):
   x=8+i*18;f[12:46,x:x+13]=VESSEL;f[44-v*3:44,x+2:x+11]=HEAT if i!=2 else COLD
  f[51:55,8:31 if g.phase else 18]=PHASE
  for i in range(g.audits):f[6:9,8+i*7:13+i*7]=AUDIT
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q299(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.vessels=(1,0,0);self.phase=self.audits=0;self.target=None;self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q299",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.vessels=(x["total"],0,0);self.phase=self.audits=0;self.target=simulate(x["total"],x["plan"]);self.bad=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3):self.vessels=move(self.vessels,a,self.phase)
  elif a==4:self.phase=1-self.phase
  elif a==5:
   if sum(self.vessels)==LEVELS[self.level_index]["total"]:self.audits+=1
   else:self.bad=True;self.lose()
  elif a==6:
   if (self.vessels,self.phase)==self.target and self.audits>=2:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
