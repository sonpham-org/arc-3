"""a133 Anonymous Robots -- create distinct local views before assigning roles."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CHAMBER,ROBOT,LANDMARK,ROLE_A,ROLE_B,VIEW,CURSOR,DISTINCT,ANONYMOUS=15,8,7,12,10,14,9,13,4,6
BAD=11
LEVELS=[
 {"name":"Place Landmark","seq":(1,)},{"name":"Select Robot","seq":(2,)},
 {"name":"Assign Role","seq":(3,1)},{"name":"Compare Views","seq":(1,2,3,4,2)},
 {"name":"Break Anonymity","seq":(1,3,2,1,4,3,2)},{"name":"Anonymous Robots","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 landmarks,roles,cursor,distinct,complementary,history,snapshot=s;lm=list(landmarks);r=list(roles)
 if a==1:lm[cursor]=1-lm[cursor];history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%4;history=(history+(2,))[-8:]
 elif a==3:r[cursor]=(r[cursor]+1)%2;history=(history+(3,))[-8:]
 elif a==4:
  signatures=[(lm[i],lm[(i-1)%4],lm[(i+1)%4]) for i in range(4)];distinct=len(set(signatures));complementary=int(distinct==4 and len(set(r))==2);history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(lm),tuple(r),cursor,distinct,complementary,history)
 return tuple(lm),tuple(r),cursor,distinct,complementary,history,snapshot
for q in LEVELS:
 s=((0,0,0,0),(0,1,0,1),0,1,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHAMBER;pts=((20,20),(44,20),(44,44),(20,44))
  for i,(x,y) in enumerate(pts):
   f[y-7:y+8,x-7:x+8]=ROBOT;f[y-3:y+4,x-3:x+4]=ROLE_A if g.roles[i]==0 else ROLE_B
   if g.landmarks[i]:f[y-10:y-7,x-5:x+6]=LANDMARK
   if i==g.cursor:f[y+9:y+12,x-8:x+9]=CURSOR
  f[54:58,8:8+g.distinct*10]=DISTINCT;f[7:10,8:8+(4-g.distinct)*10]=ANONYMOUS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A133(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a133",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.landmarks,self.roles,self.cursor,self.distinct,self.complementary,self.history,self.snapshot=((0,0,0,0),(0,1,0,1),0,1,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.landmarks,self.roles,self.cursor,self.distinct,self.complementary,self.history,self.snapshot=advance((self.landmarks,self.roles,self.cursor,self.distinct,self.complementary,self.history,self.snapshot),a)
  elif a==6:
   if (self.landmarks,self.roles,self.cursor,self.distinct,self.complementary,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
