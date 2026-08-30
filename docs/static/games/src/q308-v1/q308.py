"""q308 Asterism Ledger -- preserve experimental evidence across a physical reset."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SPACE,STAR,LINE,EVIDENCE,RESET,GOAL,BAD=3,0,15,11,14,12,10,8
LEVELS=[
 {"name":"First Orbit","stock":4,"test":(1,),"run":(2,)},{"name":"Reset Chart","stock":5,"test":(2,1),"run":(1,3)},
 {"name":"Precession","stock":6,"test":(3,2),"run":(1,2,3)},{"name":"Global Ledger","stock":7,"test":(1,3,2),"run":(2,1,3,1)},
 {"name":"Evidence Orbit","stock":8,"test":(2,3,1,2),"run":(3,1,2,3,1)},{"name":"Asterism Ledger","stock":9,"test":(1,2,3,1,3),"run":(2,3,1,2,1,3)}]
def advance(s,a):
 a0,b,c=s
 if a==1 and a0>=2:a0-=2;b+=1
 elif a==2 and b:b-=1;c+=1;a0+=1
 elif a==3 and c:c-=1;a0+=1;b+=1
 return a0,b,c
def simulate(stock,plan):
 s=(stock,0,0)
 for a in plan:s=advance(s,a)
 return s
def checksum(s):return (s[0]+2*s[1]+3*s[2])%7
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SPACE
  for i,(v,c) in enumerate(zip(g.state,(STAR,LINE,EVIDENCE))):
   x=8+i*17;f[12:39,x:x+11]=LINE;f[36-v*3:37,x+2:x+9]=c
  f[45:49,8:8+g.evidence*7]=EVIDENCE;f[52:56,8:26 if g.did_reset else 13]=RESET;f[57:60,8:8+sum(g.target)*3]=GOAL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q308(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.state=(4,0,0);self.evidence=0;self.did_reset=False;self.target=(4,0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q308",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.state=(x["stock"],0,0);self.evidence=0;self.did_reset=False;self.target=simulate(x["stock"],x["run"]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.state=advance(self.state,a)
  elif a==4:self.evidence=checksum(self.state)
  elif a==5:self.state=(x["stock"],0,0);self.did_reset=True
  elif a==6:
   if self.evidence==checksum(simulate(x["stock"],x["test"])) and self.did_reset and self.state==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
