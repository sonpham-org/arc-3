"""q758 Asterism Obligation -- keep star debts attached to identities across swaps and resets."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,STAR0,STAR1,DEBT,LIGHT,SWAP,RESET,GOAL,BAD=9,5,11,14,10,12,6,7,13,15
LEVELS=[
 {"name":"First Debt","seq":(1,5)},{"name":"Swapped Repayment","seq":(2,3,5)},
 {"name":"Two Identities","seq":(1,3,1,5,3,5)},{"name":"Reset Position","seq":(2,3,4,3,5)},
 {"name":"Persistent Obligation","seq":(1,2,3,5,4,5)},
 {"name":"Asterism Obligation","seq":(1,3,1,2,4,3,5,3,5)}]
def advance(s,a):
 ids,debts,light,resets=s;ids=list(ids);debts=list(debts);light=list(light)
 if a in (1,2):
  slot=a-1;i=ids[slot];debts[i]+=1;light[i]+=2+a
 elif a==3:ids.reverse()
 elif a==4:ids=[0,1];resets+=1
 elif a==5:
  i=ids[0]
  if debts[i]==0:return None
  light[i]-=debts[i];debts[i]=0
 return tuple(ids),tuple(debts),tuple(light),resets
for x in LEVELS:
 s=((0,1),(0,0),(0,0),0)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]
def target(x):
 s=((0,1),(0,0),(0,0),0)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD;cols=(STAR0,STAR1)
  for slot,i in enumerate(g.ids):
   x=8+slot*29;f[9:30,x:x+19]=cols[i];f[32:36,x:x+min(g.light[i],9)*2]=LIGHT
   f[39:43,x:x+g.debts[i]*5]=DEBT
  f[47:51,8:28]=SWAP;f[47:51,36:56]=RESET
  if g.resets:f[54:58,8:8+min(g.resets,5)*9]=RESET
  if tuple(g.debts)==(0,0) and any(g.light):f[55:59,42:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q758(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q758",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.ids=(0,1);self.debts=(0,0);self.light=(0,0);self.resets=0
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.ids,self.debts,self.light,self.resets),a)
   if s is None:self.bad=True;self.lose()
   else:self.ids,self.debts,self.light,self.resets=s
  elif a==6:
   if (self.ids,self.debts,self.light,self.resets)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
