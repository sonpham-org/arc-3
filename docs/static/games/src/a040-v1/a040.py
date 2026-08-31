"""a040 Tape Head -- configure a tiny finite-state read-write transition table."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,TAPE,HEAD,MARK,STATE,TABLE,GOAL,BAD=9,10,6,14,11,12,5,13,15
LEVELS=[{"name":"Read Cell","seq":(1,)},{"name":"Write Mark","seq":(2,1)},{"name":"Change State","seq":(3,1,2)},{"name":"Move Head","seq":(4,2,1,3)},{"name":"Transition Table","seq":(2,3,1,4,2,1)},{"name":"Tape Head","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 tape,head,state,table,history,configured=s;t=list(tape);tb=list(table)
 if a==1:history=history+((head,t[head],state,tuple(tb)),)
 elif a==2:t[head]=(t[head]+1+state)%3;history=history+((head,t[head],state,tuple(tb)),)
 elif a==3:state^=1;tb[state]=(tb[state]+1)%3
 elif a==4:step=-1 if tb[state]==0 else 1;head=(head+step)%len(t);state=(state+t[head])%2
 elif a==5:configured=(tuple(t),head,state,tuple(tb),history[-5:])
 return tuple(t),head,state,tuple(tb),history,configured
for x in LEVELS:
 s=((0,1,2,0,2,1,0,1),0,0,(1,2),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB
  for i,v in enumerate(g.tape):x=7+i*7;f[20:32,x:x+6]=TAPE;f[24:29,x+1:x+5]=MARK if v else TAPE
  x=7+g.head*7;f[9:19,x:x+6]=HEAD
  for i,v in enumerate(g.table):f[38+i*8:44+i*8,9:28]=TABLE;f[39+i*8:43+i*8,11:11+v*5]=STATE
  for i,_ in enumerate(g.history[-3:]):f[38+i*7:43+i*7,36:45]=MARK
  if g.configured:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A040(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a040",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tape=(0,1,2,0,2,1,0,1);self.head=self.state=0;self.table=(1,2);self.history=();self.configured=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.tape,self.head,self.state,self.table,self.history,self.configured=advance((self.tape,self.head,self.state,self.table,self.history,self.configured),a)
  elif a==6:
   if (self.tape,self.head,self.state,self.table,self.history,self.configured)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
