"""q634 Moraine Sandbox -- preserve glacier evidence while local simulations reset."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ICE,SIM0,SIM1,RAFT,CREVASSE,EVIDENCE,OUTER,GOAL,BAD=4,10,11,14,12,6,7,9,13,15
LEVELS=[
 {"name":"Twin Crevasses","seq":(1,2)},{"name":"Repeated Raft","seq":(1,1,2)},
 {"name":"Shifted Copies","seq":(1,3,2)},{"name":"Persistent Probe","seq":(1,2,4,2,1)},
 {"name":"Outer Simulation","seq":(2,3,1,1,4,2,1)},
 {"name":"Moraine Sandbox","seq":(1,3,2,2,4,2,3,1,1)}]
def advance(s,a):
 sims,cell,evidence,outer,committed=s;sims=list(sims);outer=list(outer)
 if a in (1,2):i=a-1;reading=(i+cell+sims[i])%4;sims[i]+=1;evidence=evidence+((i,reading),)
 elif a==3:sims.reverse();cell=(cell+1)%3
 elif a==4:sims=[0,0];cell=0
 elif a==5:
  if {i for i,_ in evidence}!={0,1}:return None
  outer[cell]=(sum(v for _,v in evidence)+len(evidence))%4;committed=(tuple(sims),cell,tuple(outer),len(evidence))
 return tuple(sims),cell,evidence,tuple(outer),committed
for x in LEVELS:
 s=((0,0),0,(),(0,0,0),None)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]+(5,)
def target(x):
 s=((0,0),0,(),(0,0,0),None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ICE
  for i,c in enumerate((SIM0,SIM1)):
   x=8+i*27;f[8:32,x:x+21]=c
   for n in range(6):xx=x+3+(n%3)*6;yy=11+(n//3)*10;f[yy:yy+6,xx:xx+4]=RAFT if (n+g.cell)%2 else CREVASSE
   f[34:38,x:x+min(g.sims[i],5)*4]=CREVASSE
  for j,(i,v) in enumerate(g.evidence[-6:]):f[44:49,8+j*8:14+j*8]=EVIDENCE if i else RAFT
  for i,v in enumerate(g.outer):f[52:56,8+i*16:8+i*16+v*3+4]=OUTER
  if g.committed:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q634(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q634",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=(0,0);self.cell=0;self.evidence=();self.outer=(0,0,0);self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.cell,self.evidence,self.outer,self.committed),a)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.cell,self.evidence,self.outer,self.committed=s
  elif a==6:
   if (self.sims,self.cell,self.evidence,self.outer,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
