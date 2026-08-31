"""a121 All But One -- choose the object violating exactly one grounded relation."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CHAMBER,OBJECT,REFERENCE,RELATION,SELECT,ONE,TOO_MANY,NONE,BAD=2,8,12,14,10,13,4,6,11,15
BASE=(1,2,0,1,3,2)
LEVELS=[
 {"name":"Select Candidate","seq":(1,)},{"name":"Rotate Relation","seq":(2,)},
 {"name":"Change Evidence","seq":(3,1)},{"name":"Count Exceptions","seq":(1,2,3,4,2)},
 {"name":"Exactly One","seq":(1,3,2,1,4,3,2)},{"name":"All But One","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 candidate,phase,evidence,violations,accepted,history,snapshot=s
 if a==1:candidate=(candidate+1)%6;history=(history+(1,))[-8:]
 elif a==2:phase=(phase+1)%4;history=(history+(2,))[-8:]
 elif a==3:evidence=(evidence+1)%3;history=(history+(3,))[-8:]
 elif a==4:violations=(BASE[candidate]+phase+evidence)%4;accepted=int(violations==1);history=(history+(4,))[-8:]
 elif a==5:snapshot=(candidate,phase,evidence,violations,accepted,history)
 return candidate,phase,evidence,violations,accepted,history,snapshot
for x in LEVELS:
 s=(0,0,0,1,1,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHAMBER;pts=((15,16),(31,10),(47,16),(15,42),(31,50),(47,42))
  for i,(x,y) in enumerate(pts):
   f[y-5:y+6,x-5:x+6]=OBJECT;f[y-2:y+3,x-2:x+3]=REFERENCE if (i+g.phase)%2 else RELATION
   if i==g.candidate:f[y-8:y-6,x-6:x+7]=SELECT
  for i in range(g.evidence+1):f[29:33,9+i*17:21+i*17]=REFERENCE
  col=ONE if g.violations==1 else NONE if g.violations==0 else TOO_MANY;f[54:58,8:8+max(1,g.violations)*9]=col
  if g.bad:f[1:4,18:46]=BAD
  return f
class A121(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a121",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.candidate,self.phase,self.evidence,self.violations,self.accepted,self.history,self.snapshot=(0,0,0,1,1,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.candidate,self.phase,self.evidence,self.violations,self.accepted,self.history,self.snapshot=advance((self.candidate,self.phase,self.evidence,self.violations,self.accepted,self.history,self.snapshot),a)
  elif a==6:
   if (self.candidate,self.phase,self.evidence,self.violations,self.accepted,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
