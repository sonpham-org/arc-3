"""q755 Waystation Obligation -- repay identity-bound cargo debts after swaps and policy tolls."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SAND,WALKER0,WALKER1,DEBT,CARGO,SWAP,TOLL,GOAL,BAD=9,5,11,14,10,12,6,7,13,15
LEVELS=[
 {"name":"First Cargo","seq":(1,5)},{"name":"Swapped Helper","seq":(2,3,5)},
 {"name":"Two Debts","seq":(1,3,1,5,3,5)},{"name":"Policy Toll","seq":(1,1,1,5)},
 {"name":"Persistent Obligation","seq":(1,2,3,5,4,5)},
 {"name":"Waystation Obligation","seq":(1,3,1,2,4,3,5,3,5)}]
def advance(s,a):
 ids,debts,cargo,recent,tolls=s;ids=list(ids);debts=list(debts);cargo=list(cargo)
 if a in (1,2):
  slot=a-1;i=ids[slot];punished=len(recent)==2 and recent[0]==recent[1]==slot;debts[i]+=1+int(punished);cargo[i]+=2+a;recent=(recent+(slot,))[-2:];tolls+=int(punished)
 elif a==3:ids.reverse()
 elif a==4:ids=[0,1]
 elif a==5:
  i=ids[0]
  if debts[i]==0:return None
  cargo[i]-=debts[i];debts[i]=0
 return tuple(ids),tuple(debts),tuple(cargo),recent,tolls
for x in LEVELS:
 s=((0,1),(0,0),(0,0),(),0)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]
def target(x):
 s=((0,1),(0,0),(0,0),(),0)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SAND;cols=(WALKER0,WALKER1)
  for slot,i in enumerate(g.ids):
   y=8+slot*22;f[y:y+16,8:35]=cols[i];f[y:y+5,40:40+min(g.cargo[i],7)*2]=CARGO;f[y+10:y+15,40:40+min(g.debts[i],5)*3]=DEBT
  f[52:56,8:27]=SWAP;f[52:56,37:56]=TOLL
  for i,v in enumerate(g.recent):f[57:60,8+i*12:17+i*12]=cols[v]
  if tuple(g.debts)==(0,0) and any(g.cargo):f[57:60,42:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q755(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q755",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.ids=(0,1);self.debts=(0,0);self.cargo=(0,0);self.recent=();self.tolls=0
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.ids,self.debts,self.cargo,self.recent,self.tolls),a)
   if s is None:self.bad=True;self.lose()
   else:self.ids,self.debts,self.cargo,self.recent,self.tolls=s
  elif a==6:
   if (self.ids,self.debts,self.cargo,self.recent,self.tolls)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
