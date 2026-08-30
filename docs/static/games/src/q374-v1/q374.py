"""q374 Tessera Rig -- assemble a dual-effect device and interrupt its macro on-state."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FLOOR,TESSERA,JOIN,SUPPORT,ROUTE,PHASE,LATCH,BAD=7,0,15,10,12,14,11,9,8
LEVELS=[
 {"name":"First Redirect","period":4,"window":1,"plan":(1,4,5)},
 {"name":"Joined Fold","period":5,"window":2,"plan":(2,1,4,4,5)},
 {"name":"Supported Seam","period":6,"window":3,"plan":(3,2,1,4,4,4,5)},
 {"name":"Dual Effect","period":5,"window":2,"plan":(1,3,2,4,4,5,4)},
 {"name":"Macro Window","period":7,"window":4,"plan":(2,1,3,2,4,4,4,4,5)},
 {"name":"Tessera Rig","period":8,"window":5,"plan":(3,1,2,3,1,4,4,4,4,4,5,4)}]
def advance(s,a,x):
 counts,route,payload,phase,latched=s;counts=list(counts)
 if a in (1,2,3):counts[a-1]+=1;route=(route+a+counts[a-1])%5;payload=(payload+route+a)%6
 elif a==4:phase=(phase+1)%x["period"];payload=(payload+route+phase)%6
 elif a==5:
  if phase!=x["window"] or not sum(counts):return None
  latched=True;route=(route+sum(counts))%5;payload=(payload+2)%6
 return tuple(counts),route,payload,phase,latched
def target(x):
 s=((0,0,0),0,0,0,False)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=FLOOR
  cols=(TESSERA,JOIN,SUPPORT)
  for i,n in enumerate(g.counts):
   x=8+i*18;f[7:10,x:x+13]=cols[i]
   for j in range(n):f[10+j*7:16+j*7,x:x+13]=cols[i]
  f[43:48,7:7+g.route*11]=ROUTE;f[50:54,7:7+g.phase*6]=PHASE
  if g.latched:f[56:60,12:52]=LATCH
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q374(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.counts=(0,0,0);self.route=self.payload=self.phase=0;self.latched=False;self.bad=False;self.target=target(LEVELS[0])
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q374",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.counts=(0,0,0);self.route=self.payload=self.phase=0;self.latched=False;self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.counts,self.route,self.payload,self.phase,self.latched),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.counts,self.route,self.payload,self.phase,self.latched=s
  elif a==6:
   if (self.counts,self.route,self.payload,self.phase,self.latched)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
