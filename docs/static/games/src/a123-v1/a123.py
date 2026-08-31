"""a123 Same Row Different Role -- preserve teams while separating inferred roles."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,GRID,TEAM_A,TEAM_B,ROLE_A,ROLE_B,ROLE_C,BEHAVIOR,DUPLICATE,BAD=4,8,12,14,9,10,13,11,6,15
LEVELS=[
 {"name":"Change Role","seq":(1,)},{"name":"Select Agent","seq":(2,)},
 {"name":"Change Appearance","seq":(3,1)},{"name":"Check Columns","seq":(1,2,3,4,2)},
 {"name":"Preserve Teams","seq":(1,3,2,1,4,3,2)},{"name":"Same Row Different Role","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 roles,cursor,appearance,duplicates,team_errors,history,snapshot=s;r=list(roles)
 if a==1:r[cursor]=(r[cursor]+1)%3;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%9;history=(history+(2,))[-8:]
 elif a==3:appearance=(appearance+1)%3;history=(history+(3,))[-8:]
 elif a==4:
  duplicates=sum(3-len({r[row*3+col] for row in range(3)}) for col in range(3));team_errors=sum(int(r[row*3]==r[row*3+1]==r[row*3+2]) for row in range(3));history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(r),cursor,appearance,duplicates,team_errors,history)
 return tuple(r),cursor,appearance,duplicates,team_errors,history,snapshot
for q in LEVELS:
 s=((0,1,2,1,2,0,2,0,1),0,0,0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GRID;cols=(ROLE_A,ROLE_B,ROLE_C)
  for i,role in enumerate(g.roles):
   x=10+(i%3)*16;y=11+(i//3)*15;f[y:y+12,x:x+12]=TEAM_A if i//3%2==0 else TEAM_B;f[y+3:y+9,x+3:x+9]=cols[(role+g.appearance)%3]
   if i==g.cursor:f[y-3:y,x:x+12]=BEHAVIOR
  f[54:58,8:8+g.duplicates*7]=DUPLICATE;f[7:10,8:8+g.team_errors*10]=BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A123(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a123",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.roles,self.cursor,self.appearance,self.duplicates,self.team_errors,self.history,self.snapshot=((0,1,2,1,2,0,2,0,1),0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.roles,self.cursor,self.appearance,self.duplicates,self.team_errors,self.history,self.snapshot=advance((self.roles,self.cursor,self.appearance,self.duplicates,self.team_errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.roles,self.cursor,self.appearance,self.duplicates,self.team_errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
