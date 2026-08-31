"""a200 Fault-Tolerant Assembly -- survive every single post-construction failure."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FACTORY,PRIMARY,BACKUP,FAILED,CURSOR,LINK,ROBUST,SINGLE_POINT,OUTPUT=10,1,12,14,6,13,8,4,9,5
BAD=15
LEVELS=[
 {"name":"Toggle Component","seq":(1,)},{"name":"Move Cursor","seq":(2,)},
 {"name":"Choose Failure","seq":(3,1)},{"name":"Test Every Failure","seq":(1,2,3,4,2)},
 {"name":"Remove Common Point","seq":(1,3,2,1,4,3,2)},{"name":"Fault-Tolerant Assembly","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def audit(enabled):
 failures=0
 for failed in range(10):
  failures+=int(any(not any(((enabled>>(stage*2+k))&1) and stage*2+k!=failed for k in range(2)) for stage in range(5)))
 return 10-failures,failures
def advance(s,a):
 enabled,cursor,failure,robust,single_points,history,snapshot=s
 if a==1:enabled^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%10;history=(history+(2,))[-8:]
 elif a==3:failure=(failure+1)%10;history=(history+(3,))[-8:]
 elif a==4:robust,single_points=audit(enabled);history=(history+(4,))[-8:]
 elif a==5:snapshot=(enabled,cursor,failure,robust,single_points,history)
 return enabled,cursor,failure,robust,single_points,history,snapshot
for q in LEVELS:
 s=(0b1111111111,0,3,10,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=FACTORY
  for stage in range(5):
   x=8+stage*10;f[18:22,x+7:x+10]=LINK;f[39:43,x+7:x+10]=LINK
   for lane in range(2):
    i=stage*2+lane;y=10+lane*25;col=FAILED if i==g.failure else PRIMARY if lane==0 else BACKUP;f[y:y+13,x:x+8]=col if (g.enabled>>i)&1 else BG
    if i==g.cursor:f[y-3:y,x:x+8]=CURSOR
  f[25:34,52:58]=OUTPUT;f[53:57,8:8+min(10,g.robust)*4]=ROBUST;f[53:57,49:49+min(3,g.single_points)*3]=SINGLE_POINT
  if g.bad:f[1:4,18:46]=BAD
  return f
class A200(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a200",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.enabled,self.cursor,self.failure,self.robust,self.single_points,self.history,self.snapshot=(0b1111111111,0,3,10,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.enabled,self.cursor,self.failure,self.robust,self.single_points,self.history,self.snapshot=advance((self.enabled,self.cursor,self.failure,self.robust,self.single_points,self.history,self.snapshot),a)
  elif a==6:
   if (self.enabled,self.cursor,self.failure,self.robust,self.single_points,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
