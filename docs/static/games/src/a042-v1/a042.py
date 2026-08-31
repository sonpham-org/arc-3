"""a042 Semaphore Garden -- synchronize two workers through one tunnel."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SOIL,LEAF,TUNNEL,WORK_A,WORK_B,TOKEN,FLOWER,LOG,BAD=2,9,10,8,12,14,11,13,6,15
LEVELS=[
 {"name":"Place Permit","seq":(1,)},{"name":"First Worker","seq":(1,3)},
 {"name":"Release Permit","seq":(1,3,2,4)},{"name":"Arrival Orders","seq":(2,4,1,3,3)},
 {"name":"Mutual Exclusion","seq":(1,3,3,2,4,4,1)},{"name":"Semaphore Garden","seq":(2,4,1,3,3,2,4,1,3)},
]
def advance(s,a):
 pa,pb,permit,owner,bloom,log,snapshot=s
 if a==1:permit=0 if permit==1 else 1;log=(log+(1,))[-8:]
 elif a==2:permit=0 if permit==2 else 2;log=(log+(2,))[-8:]
 elif a==3:
  if pa==2 and (permit!=1 or owner not in (-1,0)):pass
  else:
   if pa==2:owner=0
   pa=min(5,pa+1)
   if pa>3 and owner==0:owner=-1;bloom=(bloom+1)%5
  log=(log+(3,))[-8:]
 elif a==4:
  if pb==2 and (permit!=2 or owner not in (-1,1)):pass
  else:
   if pb==2:owner=1
   pb=min(5,pb+1)
   if pb>3 and owner==1:owner=-1;bloom=(bloom+2)%5
  log=(log+(4,))[-8:]
 elif a==5:snapshot=(pa,pb,permit,owner,bloom,log)
 return pa,pb,permit,owner,bloom,log,snapshot
for x in LEVELS:
 s=(0,0,0,-1,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,5:59]=SOIL
  for y in range(9,55,9):f[y:y+3,8:56]=LEAF
  f[24:40,24:40]=TUNNEL;f[27:37,27:37]=BG
  xa=7+g.pa*7;xb=50-g.pb*7;f[18:26,xa:xa+6]=WORK_A;f[39:47,xb:xb+6]=WORK_B
  f[10:17,25:31]=TOKEN if g.permit==1 else LEAF;f[47:54,33:39]=TOKEN if g.permit==2 else LEAF
  for i in range(g.bloom):f[7+i*10:12+i*10,51:56]=FLOWER
  for i,v in enumerate(g.log[-8:]):f[55:58,10+i*5:14+i*5]=WORK_A if v==3 else WORK_B if v==4 else LOG
  if g.bad:f[1:4,18:46]=BAD
  return f
class A042(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a042",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pa,self.pb,self.permit,self.owner,self.bloom,self.log,self.snapshot=(0,0,0,-1,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pa,self.pb,self.permit,self.owner,self.bloom,self.log,self.snapshot=advance((self.pa,self.pb,self.permit,self.owner,self.bloom,self.log,self.snapshot),a)
  elif a==6:
   if (self.pa,self.pb,self.permit,self.owner,self.bloom,self.log,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
