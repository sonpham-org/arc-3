"""a149 Controllable Object -- identify weak agency through orthogonal interventions."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,ARENA,PIECE_A,PIECE_B,SOCKET,CURSOR,CMD_X,CMD_Y,EVIDENCE,CONTROLLED=0,8,12,14,10,13,9,11,4,6
BAD=15
CONTROL=2
LEVELS=[
 {"name":"Command Across","seq":(1,)},{"name":"Command Down","seq":(2,)},
 {"name":"Select Candidate","seq":(3,1)},{"name":"Compare Responses","seq":(1,2,3,4,2)},
 {"name":"Identify Control","seq":(1,3,2,1,4,3,2)},{"name":"Controllable Object","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 positions,cursor,commands,evidence,identified,history,snapshot=s;p=[list(x) for x in positions]
 if a in (1,2):
  for i in range(6):
   p[i][0]=(p[i][0]+1)%6;p[i][1]=(p[i][1]+(i%2))%6
  p[CONTROL][a-1]=(p[CONTROL][a-1]+1)%6;commands=(commands+(a,))[-4:];history=(history+(a,))[-8:]
 elif a==3:cursor=(cursor+1)%6;history=(history+(3,))[-8:]
 elif a==4:evidence=sum(int(x==1)+int(x==2) for x in commands);identified=int(cursor==CONTROL and evidence>=2);history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(map(tuple,p)),cursor,commands,evidence,identified,history)
 return tuple(map(tuple,p)),cursor,commands,evidence,identified,history,snapshot
for q in LEVELS:
 s=(((0,0),(1,2),(2,4),(3,1),(4,3),(5,5)),0,(),0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARENA;f[45:55,45:55]=SOCKET
  for i,(x,y) in enumerate(g.positions):
   px=9+x*8;py=9+y*7;f[py:py+7,px:px+7]=CONTROLLED if i==CONTROL and g.identified else PIECE_A if i%2==0 else PIECE_B
   if i==g.cursor:f[py-3:py,px:px+7]=CURSOR
  f[7:10,8:28]=CMD_X;f[7:10,31:51]=CMD_Y;f[54:58,8:8+g.evidence*7]=EVIDENCE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A149(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a149",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.positions,self.cursor,self.commands,self.evidence,self.identified,self.history,self.snapshot=(((0,0),(1,2),(2,4),(3,1),(4,3),(5,5)),0,(),0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.positions,self.cursor,self.commands,self.evidence,self.identified,self.history,self.snapshot=advance((self.positions,self.cursor,self.commands,self.evidence,self.identified,self.history,self.snapshot),a)
  elif a==6:
   if (self.positions,self.cursor,self.commands,self.evidence,self.identified,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
