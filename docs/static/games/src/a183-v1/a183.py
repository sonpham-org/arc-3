"""a183 Universal Tester -- select a tiny suite distinguishing every candidate pair."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CONSOLE,MACHINE_A,MACHINE_B,TEST,SELECTED,CURSOR,DISTINGUISHED,MISSED,REDUNDANT=4,8,12,14,10,13,11,4,6,9
BAD=15
SIGNATURES=(0b0011,0b0101,0b1001,0b0110,0b1010,0b1100)
LEVELS=[
 {"name":"Select Test","seq":(1,)},{"name":"Move Cursor","seq":(2,)},
 {"name":"Probe Machines","seq":(3,1)},{"name":"Distinguish Every Pair","seq":(1,2,3,4,2)},
 {"name":"Remove Redundancy","seq":(1,3,2,1,4,3,2)},{"name":"Universal Tester","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 selected,cursor,probe,distinguished,missed,redundant,history,snapshot=s
 if a==1:selected^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%4;history=(history+(2,))[-8:]
 elif a==3:probe=(probe+1)%6;history=(history+(3,))[-8:]
 elif a==4:
  distinguished=sum(int(((SIGNATURES[i]^SIGNATURES[j])&selected)!=0) for i in range(6) for j in range(i+1,6));missed=15-distinguished;redundant=max(0,selected.bit_count()-2);history=(history+(4,))[-8:]
 elif a==5:snapshot=(selected,cursor,probe,distinguished,missed,redundant,history)
 return selected,cursor,probe,distinguished,missed,redundant,history,snapshot
for q in LEVELS:
 s=(0b0011,0,0,12,3,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CONSOLE
  for i in range(6):x=8+(i%3)*18;y=13+(i//3)*20;f[y:y+14,x:x+14]=MACHINE_A if i%2==0 else MACHINE_B
  for i in range(4):x=10+i*12;f[49:56,x:x+9]=SELECTED if (g.selected>>i)&1 else TEST;f[46:49,x:x+9]=CURSOR if i==g.cursor else CONSOLE
  f[7:10,8:8+min(15,g.distinguished)*3]=DISTINGUISHED;f[54:58,8:8+g.missed*5]=MISSED;f[54:58,50:50+g.redundant*2]=REDUNDANT
  if g.bad:f[1:4,18:46]=BAD
  return f
class A183(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a183",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.selected,self.cursor,self.probe,self.distinguished,self.missed,self.redundant,self.history,self.snapshot=(0b0011,0,0,12,3,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.selected,self.cursor,self.probe,self.distinguished,self.missed,self.redundant,self.history,self.snapshot=advance((self.selected,self.cursor,self.probe,self.distinguished,self.missed,self.redundant,self.history,self.snapshot),a)
  elif a==6:
   if (self.selected,self.cursor,self.probe,self.distinguished,self.missed,self.redundant,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
