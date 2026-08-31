"""q763 Impeller Obligation -- repay torque debt to blade identities across ring rotation."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,RIDER0,RIDER1,RIDER2,DEBT,TORQUE,ROTATE,SAMPLE,GOAL,BAD=9,5,11,14,12,10,6,7,4,13,15
LEVELS=[
 {"name":"First Torque","seq":(1,5)},{"name":"Full Rotation","seq":(1,2,2,2,5)},
 {"name":"Two Riders","seq":(1,2,1,5,2,2,5)},{"name":"Sampled Debt","seq":(1,4,2,2,2,5)},
 {"name":"Three Obligations","seq":(1,2,1,2,1,5,2,5,2,5)},
 {"name":"Impeller Obligation","seq":(1,3,2,1,4,5,2,2,5)}]
def advance(s,a):
 ids,debts,torque,direction,evidence,cost=s;ids=list(ids);debts=list(debts);torque=list(torque)
 if a==1:i=ids[0];debts[i]+=1;torque[i]+=3
 elif a==2:ids=ids[1:]+ids[:1] if direction>0 else ids[-1:]+ids[:-1]
 elif a==3:direction*=-1
 elif a==4:cost+=2 if evidence and evidence[-1]==tuple(debts) else 1;evidence=evidence+(tuple(debts),)
 elif a==5:
  i=ids[0]
  if debts[i]==0:return None
  torque[i]-=debts[i];debts[i]=0
 return tuple(ids),tuple(debts),tuple(torque),direction,evidence,cost
for x in LEVELS:
 s=((0,1,2),(0,0,0),(0,0,0),1,(),0)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]
def target(x):
 s=((0,1,2),(0,0,0),(0,0,0),1,(),0)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD;cols=(RIDER0,RIDER1,RIDER2)
  for slot,i in enumerate(g.ids):
   x=7+slot*18;f[9:29,x:x+14]=cols[i];f[32:36,x:x+min(g.torque[i],7)*2]=TORQUE;f[39:43,x:x+min(g.debts[i],5)*3]=DEBT
  f[47:51,8:28]=ROTATE;f[47:51,36:56]=SAMPLE
  f[54:58,8:8+min(g.cost,9)*5]=SAMPLE
  if tuple(g.debts)==(0,0,0) and any(g.torque):f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q763(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q763",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.ids=(0,1,2);self.debts=(0,0,0);self.torque=(0,0,0);self.direction=1;self.evidence=();self.cost=0
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.ids,self.debts,self.torque,self.direction,self.evidence,self.cost),a)
   if s is None:self.bad=True;self.lose()
   else:self.ids,self.debts,self.torque,self.direction,self.evidence,self.cost=s
  elif a==6:
   if (self.ids,self.debts,self.torque,self.direction,self.evidence,self.cost)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
